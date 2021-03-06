# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function, unicode_literals
import numpy as np
import gdspy
import uuid
import picwriter.toolkit as tk
from picwriter.components.waveguide import Waveguide

class ZeroLengthCavity(gdspy.Cell):
    """ Zero-Length Cavity Cell class (subclass of gdspy.Cell).

        Args:
           * **wgt** (WaveguideTemplate):  WaveguideTemplate object
           * **nbr_holes** (float): Number of holes in the mirror.
           * **period** (float): Period of the repeated unit.
           * **radius** (float): Radius of the holes of the mirror.
           * **radius_taper** (float): Radius of the smallest hole of the taper. Defaults to radius/2.
           * **gap** (float): Gap between the cavity and the waveguide.
           * **wgt_beam_length** (float): Extra length of nanobeam that is simple  waveguide.

        Keyword Args:
           * **nbr_taper** (float): Number of holes in the taper region between the mirror and the waveguide. Defaults to 4.
           * **taper_type** (string): Determines the radius of the taper holes. 'ratio' corresponds to a constant radius/period ratio. 'FF' corresponds to a linearly decreasing fill factor (hole area/unit cell area). Defaults to 'FF'.
           * **port** (tuple): Cartesian coordinate of the input port.  Defaults to (0,0).
           * **direction** (string): Direction that the component will point *towards*, can be of type `'NORTH'`, `'WEST'`, `'SOUTH'`, `'EAST'`, OR an angle (float, in radians)

        Members:
           * **portlist** (dict): Dictionary with the relevant port information

        Portlist format:
           * portlist['input'] = {'port': (x1,y1), 'direction': 'dir1'}
           * portlist['output'] = {'port': (x2, y2), 'direction': 'dir2'}

        Where in the above (x1,y1) is the same as the 'port' input, (x2, y2) is the end of the DBR, and 'dir1', 'dir2' are of type `'NORTH'`, `'WEST'`, `'SOUTH'`, `'EAST'`, *or* an angle in *radians*.
        'Direction' points *towards* the waveguide that will connect to it.

    """
    def __init__(self, wgt, nbr_holes, period, radius, radius_taper, gap, wgt_beam_length, nbr_taper=4, taper_type='FF', port=(0,0), direction='EAST'):
        gdspy.Cell.__init__(self, "ZLCavity--"+str(uuid.uuid4()))

        self.portlist = {}

        self.port = port
        self.direction = direction
        self.nbr_holes = nbr_holes
        self.nbr_taper = nbr_taper
        self.radius = radius
        self.period = period
        self.radius_taper = radius_taper
        self.taper_type = taper_type
        self.gap = gap
        self.wgt_beam_length = wgt_beam_length

        self.wgt = wgt
        self.wg_spec = {'layer': wgt.wg_layer, 'datatype': wgt.wg_datatype}
        self.clad_spec = {'layer': wgt.clad_layer, 'datatype': wgt.clad_datatype}
        
        if taper_type=="FF":
            self.taper_length = nbr_taper*period
            self.total_length = nbr_holes*period + 2*self.taper_length + 2*self.wgt_beam_length
            self.trace=[port, tk.translate_point(port, self.total_length, direction)]
        elif taper_type=="ratio":
            self.taper_length = period/radius*(radius*nbr_taper + (nbr_taper+1)*(radius_taper-radius)/2)
            self.total_length = nbr_holes*period + 2*self.taper_length + 2*self.wgt_beam_length
            self.trace=[port, tk.translate_point(port, self.total_length, direction)]

        self.type_check_trace()
        self.build_cell()
        self.build_ports()

    def type_check_trace(self):
        trace = []
        """ Round each trace value to the nearest 1e-6 -- prevents
        some typechecking errors
        """
        for t in self.trace:
            trace.append((round(t[0], 6), round(t[1], 6)))
        self.trace = trace

    def build_cell(self):
        # Sequentially build all the geometric shapes using gdspy path functions
        # for waveguide, then add it to the Cell
        angle = tk.get_exact_angle(self.trace[0], self.trace[1])
        
        # Add bus waveguide, and cladding
        bus = gdspy.Path(self.wgt.wg_width, self.trace[0])
        bus.segment(self.total_length, direction=angle, **self.wg_spec)
        # Cladding for bus waveguide
        bus_clad = gdspy.Path(2*self.wgt.clad_width+self.wgt.wg_width, self.trace[0])
        bus_clad.segment(self.total_length, direction=angle, **self.clad_spec)

        self.add(bus)
        self.add(bus_clad)        

        # Add nanobeam waveguide
        beam_x = self.trace[0][0] - np.sin(angle)*(self.gap + 2*self.wgt.wg_width)
        beam_y = self.trace[0][1] + np.cos(angle)*(self.gap + 2*self.wgt.wg_width)
        nanobeam = gdspy.Path(self.wgt.wg_width, (beam_x,beam_y))
        nanobeam.segment(self.total_length, direction=angle, **self.wg_spec)
        # Cladding for nanobeam
        nanobeam_clad = gdspy.Path(2*self.wgt.clad_width+self.wgt.wg_width, (beam_x,beam_y))
        nanobeam_clad.segment(self.total_length, direction=angle, **self.clad_spec)        

        """ Add the mirror holes """
        startx = beam_x + np.cos(angle)*(self.wgt_beam_length + self.taper_length + self.period/2)
        starty = beam_y + np.sin(angle)*(self.wgt_beam_length + self.taper_length + self.period/2)
        hole_list = []
        for i in range(int(self.nbr_holes)):
            x = startx + i*np.cos(angle)*self.period
            y = starty + i*np.sin(angle)*self.period
            hole_list.append(gdspy.Round((x,y), self.radius))

        """ Add the taper holes """
        if self.taper_type=="FF":
            startx_in = beam_x + np.cos(angle)*(self.wgt_beam_length + self.period/2)
            startx_out = beam_x + np.cos(angle)*(self.total_length - self.wgt_beam_length - self.period/2)
            starty_in = beam_y + np.sin(angle)*(self.wgt_beam_length + self.period/2)
            starty_out = beam_y + np.sin(angle)*(self.total_length - self.wgt_beam_length - self.period/2)
            taper_list_in = []
            taper_list_out = []
            for i in range(int(self.nbr_taper)):
                fill_factor = np.pi*np.square(self.radius_taper/self.period) + i*np.pi*(np.square(self.radius/self.period) - np.square(self.radius_taper/self.period))/(self.nbr_taper - 1)
                taper_radii = np.sqrt(fill_factor/np.pi)*self.period
                x_in = startx_in + i*np.cos(angle)*self.period
                y_in = starty_in + i*np.sin(angle)*self.period
                taper_list_in.append(gdspy.Round((x_in,y_in), taper_radii))
                x_out = startx_out - i*np.cos(angle)*self.period
                y_out = starty_out - i*np.sin(angle)*self.period
                taper_list_out.append(gdspy.Round((x_out,y_out), taper_radii))
        elif self.taper_type=="ratio":
            startx_in = beam_x + np.cos(angle)*self.wgt_beam_length
            startx_out = beam_x + np.cos(angle)*(self.total_length - self.wgt_beam_length)
            starty_in = beam_y + np.sin(angle)*self.wgt_beam_length
            starty_out = beam_y + np.sin(angle)*(self.total_length - self.wgt_beam_length)
            taper_list_in = []
            taper_list_out = []
            for i in range(int(self.nbr_taper)):
                ratio = self.period/self.radius
                taper_radii = self.radius_taper + i*(self.radius-self.radius_taper)/(self.nbr_taper-1)
                taper_period = taper_radii*ratio
                x_in = startx_in + i*np.cos(angle)*taper_period
                y_in = starty_in + i*np.sin(angle)*taper_period
                taper_list_in.append(gdspy.Round((x_in,y_in), taper_radii))
                x_out = startx_out - i*np.cos(angle)*taper_period
                y_out = starty_out - i*np.sin(angle)*taper_period
                taper_list_out.append(gdspy.Round((x_out,y_out), taper_radii))

        for hole in hole_list:
            nanobeam = gdspy.fast_boolean(nanobeam,hole,'xor')
        for hole_in in taper_list_in:
            nanobeam = gdspy.fast_boolean(nanobeam,hole_in,'xor')        
        for hole_out in taper_list_out:
            nanobeam = gdspy.fast_boolean(nanobeam,hole_out,'xor')
            
        self.add(nanobeam)
        self.add(nanobeam_clad)

    def build_ports(self):
        # Portlist format:
        # example: example:  {'port':(x_position, y_position), 'direction': 'NORTH'}
        self.portlist["input"] = {'port':self.trace[0], 'direction':tk.flip_direction(self.direction)}
        self.portlist["output"] = {'port':self.trace[1], 'direction':self.direction}

if __name__ == "__main__":
    from picwriter.components import *
    top = gdspy.Cell("top")
    wgt = WaveguideTemplate(wg_width=1.0, clad_width=10.0, bend_radius=50, resist='+')

    wg1=Waveguide([(0,0), (100,0)], wgt)
    tk.add(top, wg1)

    zlc1 = ZeroLengthCavity(wgt, 8, 0.4, 0.1, 0.08, 0.05, 1, **wg1.portlist["output"])
    tk.add(top, zlc1)

    (x1, y1) = zlc1.portlist["output"]["port"]
    wg2=Waveguide([(x1,y1),
                   (x1+100,y1),
                   (x1+100,y1+100)], wgt)
    tk.add(top, wg2)

    zlc2 = ZeroLengthCavity(wgt, 20, 0.4, 0.1, 0.08, 0.05, 1, 6, taper_type='ratio', **wg2.portlist["output"])
    tk.add(top, zlc2)

    (x2, y2) = zlc2.portlist["output"]["port"]
    wg3=Waveguide([(x2,y2), (x2, y2+100.0),(x2+100,y2+200),(x2+100,y2+300)], wgt)
    tk.add(top, wg3)

    gdspy.LayoutViewer()
#    gdspy.write_gds('dbr.gds', unit=1.0e-6, precision=1.0e-9)
