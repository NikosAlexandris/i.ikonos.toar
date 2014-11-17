#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MODULE:         i.fusion.hpf

AUTHOR(S):      Nikos Alexandris <nik@nikosalexandris.net>
                Converted from a bash shell script | Trikala, November 2014


PURPOSE:        Converting IKONOS DN values to Spectral Radiance or Reflectance


                Spectral Radiance -------------------------------------------

                    for spectral band λ at the sensor’s aperture in
                    watts / (meter squared * ster * µm)

                    L(λ) = 10^4 x DN(λ) / CalCoef(λ) x Bandwidth(λ)    (1)

                where:
                - CalCoef_λ = Radiometric calibration coefficient [DN/(mW/cm 2- sr)]
                - Bandwidth_λ = Bandwidth of spectral band λ (nm)

                Alt. unit(s) notation:
                - (W/m2/μm/sr)
                - W / m^2 * ster * micro-m
                - W·sr−1·m−2 | "The SI unit of radiance is watts per steradian
                per square metre" <http://en.wikipedia.org/wiki/Radiance>


                Planetary Reflectance ---------------------------------------

                    ρ(p) = π x L(λ) x d^2 / ESUN(λ) x cos(θ(S))

                where:
                - ρ: Unitless Planetary Reflectance
                - π: Mathematical constant
                - L(λ): Spectral Radiance from equation (1)
                - d: Earth-Sun distance in astronomical units [calculated using
                AcquisitionTime class]


                Sources -----------------------------------------------------

                - "IKONOS Planetary Reflectance and Mean Solar
                Exoatmospheric Irradiance", by Martin Taylor, Geoeye.
                - <http://landsat.usgs.gov/how_is_radiance_calculated.php>


 COPYRIGHT:    (C) 2014 by the GRASS Development Team

               This program is free software under the GNU General Public
               License (>=v2). Read the file COPYING that comes with GRASS
               for details.
"""

#%Module
#%  description: Converting IKONOS digital numbers (radiometrically corrected) to Top-of-Atmosphere Spectral Radiance or Reflectance  (Krause, 2005)
#%  keywords: imagery, radiometric conversion, radiance, reflectance, IKONOS
#%End

#%flag
#%  key: r
#%  description: Convert to at-sensor spectral radiance
#%end

#%flag
#%  key: k
#%  description: Keep current computational region settings
#%end

#%option G_OPT_R_INPUTS
#% key: band
#% key_desc: band name
#% type: string
#% description: IKONOS acquired spectral band(s) (DN values).
#% multiple: yes
#% required: yes
#%end

#%option G_OPT_R_BASENAME_OUTPUT
#% key: outputsuffix
#% key_desc: suffix string
#% type: string
#% label: 
#% description: Suffix for spectral radiance or reflectance output image(s)
#% required: yes
#% answer: toar
#%end

#%option
#% key: utc
#% key_desc: YYYY_MM_DDThh:mm:ss:ddddddZ;
#% type: string
#% description: Coordinated Universal Time
#% guisection: Metadata
#% required: yes
#%end

#%option
#% key: doy
#% key_desc: day of year
#% type: integer
#% description: User defined aquisition's Day of Year to calculate Earth-Sun distance
#% options: 1-365
#% guisection: Metadata
#% required: no
#%end

#%option
#% key: sea
#% key_desc: degrees
#% type: double
#% description: Aquisition's Sun Elevation Angle
#% options: 0.0 - 90.0
#% guisection: Metadata
#% required: yes
#%end


# librairies
import os
import sys
sys.path.insert(1, os.path.join(os.path.dirname(sys.path[0]),
                                'etc', 'i.ikonos.toar'))

import atexit
from datetime import datetime

import grass.script as grass
from grass.pygrass.modules.shortcuts import general as g
#from grass.pygrass.raster.abstract import Info
import math
from utc_to_esd import AcquisitionTime, jd_to_esd


# globals -------------------------------------------------------------------
acq_tim = ''
tmp = ''
tmp_rad = ''
tmp_toar = ''

# constants
"""
Band Parameters. Coefficients, updated on 2001-02-22, are for 11-bit products.
Taylor, 2005.

# IKONOS Band (λ)                           1st column (dictionary keys)
# CalCoef(λ) Pre  2/22/01 (DN/(mW/cm2-sr))  2nd column (1st in tuple)
# CalCoef(λ) Post 2/22/01 (DN/(mW/cm2-sr))  3rd column (2nd in tuple)
# Effective Bandwidthλ (nm)                 4th column (3rd in tuple)
# Esun(λ) (W/m2/μm)                         5th column (4th in tuple)
"""
CC = {'Pan':   (161, 161, 403.0, 1375.8),  # Note: Pan is "TDI-13"
      'Blue':  (633, 728, 071.3, 1930.9),
      'Green': (649, 727, 088.6, 1854.8),
      'Red':   (840, 949, 065.8, 1556.5),
      'NIR':   (746, 843, 095.4, 1156.9)}

cc_update = datetime(2001, 2, 22)

spectral_bands = CC.keys()

# string for metadata
source1_rad = source1_toar = 'Martin Taylor, 2005. '
'"IKONOS Planetary Reflectance and Mean Solar Exoatmospheric Irradiance".'
source2_rad = source2_toar = ""  # Add some source2?


# helper functions ----------------------------------------------------------
def cleanup():
    """Clean up temporary files"""
    grass.run_command('g.remove', flags='f', type="rast",
                      pattern='tmp.%s*' % os.getpid(), quiet=True)


def run(cmd, **kwargs):
    """Help function executing grass commands with 'quiet=True'"""
    grass.run_command(cmd, quiet=True, **kwargs)


#def dn_to_rad(dn, bw, cc):
#    """Converting DN to Spectral Radiance. Required inputs:
#    - dn: Digital Numbers (raster map)
#    - bw: Effective Bandwidth
#    - cc: Calibration Coefficient"""
#    rad = "%s = 10**4 * %s / %f * %f" % (rad, dn, cc, bw)
#    grass.mapcalc(rad)


def main():

    global acq_time, esd
    """1st, get input, output, options and flags"""

    spectral_bands = options['band'].split(',')
    outputsuffix = options['outputsuffix']
    utc = options['utc']
    doy = options['doy']
    sea = options['sea']
    radiance = flags['r']
    keep_region = flags['k']

    mapset = grass.gisenv()['MAPSET']  # Current Mapset?
    imglst = [spectral_bands]
#    images = {}
#    for img in imglst:  # Retrieving Image Info
#        images[img] = Info(img, mapset)
#        images[img].read()

    # -----------------------------------------------------------------------
    # Temporary Region and Files
    # -----------------------------------------------------------------------

    if not keep_region:
        grass.use_temp_region()  # to safely modify the region
    tmpfile = grass.tempfile()  # Temporary file - replace with os.getpid?
    tmp = "tmp." + grass.basename(tmpfile)  # use its basename

    # -----------------------------------------------------------------------
    # Global Metadata: Earth-Sun distance, Sun Zenith Angle
    # -----------------------------------------------------------------------

    acq_utc = AcquisitionTime(utc)  # will hold esd (earth-sun distance)
    acq_dat = datetime(acq_utc.year, acq_utc.month, acq_utc.day)

    # Earth-Sun distance
    if doy:
        esd = jd_to_esd(int(doy))

    elif utc:
        esd = acq_utc.esd

    else:
        grass.fatal(_("Either the UTC string or "
                      "the Day-of-Year (doy) are required!"))

    sza = 90 - float(sea)  # Sun Zenith Angle based on Sun Elevation Angle

    # -----------------------------------------------------------------------
    # Loop processing over all bands
    # -----------------------------------------------------------------------
    for band in spectral_bands:

        global tmp_rad

        g.message("|* Processing the %s spectral band" % band, flags='i')

        if not keep_region:
            g.message("\n|! Matching region to %s" % band)  # set region
            run('g.region', rast=band)   # ## FixMe

        # -------------------------------------------------------------------
        # Converting to Spectral Radiance
        # -------------------------------------------------------------------

        msg = "\n|> Converting to Spectral Radiance: " \
#            "L(λ) = 10^4 x DN(λ) / CalCoef(λ) x Bandwidth(λ)"  # Unicode? ##
        g.message(msg)

        # -------------------------------------------------------------------
        # Band dependent metadata for Spectral Radiance
        # -------------------------------------------------------------------

        # Why is this necessary?  Any function to remove the mapsets name?
        if '@' in band:
            band_key = (band.split('@')[0])
        else:
            band_key = band

        # get coefficients
        if acq_dat < cc_update:
            g.message("\n|! Using Pre-2001 Calibration Coefficient values",
                      flags='i')
            cc = float(CC[band_key][0])
        else:
            cc = float(CC[band_key][1])

        # get bandwidth
        bw = float(CC[band_key][2])

        # inform
        msg = "   [Calibration Coefficient=%d, Bandwidth=%.1f]" \
            % (cc, bw)
        g.message(msg)

        # convert
        tmp_rad = "%s.Radiance" % tmp  # Temporary Map
        rad = "%s = 10^4 * %s / %f * %f" \
            % (tmp_rad, band, cc, bw)
        grass.mapcalc(rad)

        # string for metadata
        history_rad = rad
        history_rad += "Calibration Coefficient=%d; Effective Bandwidth=%.1f" \
            % (cc, bw)
        title_rad = "%s band (Spectral Radiance)" % band
        units_rad = "W / m2 / μm / ster"
        description_rad = "At-sensor %s band spectral Radiance (W/m2/μm/sr)" \
            % band

        if not radiance:

            # ---------------------------------------------------------------
            # Converting to Top-of-Atmosphere Reflectance
            # ---------------------------------------------------------------

            global tmp_toar

            msg = "\n|> Converting to Top-of-Atmosphere Reflectance" \
#            "ρ(p) = π x L(λ) x d^2 / ESUN(λ) x cos(θ(S))"  # Unicode? ######
            g.message(msg)

            # ---------------------------------------------------------------
            # Band dependent metadata for Spectral Radiance
            # ---------------------------------------------------------------

            # get esun
            esun = CC[band_key][3]

            # inform
            msg = "   [Earth-Sun distane=%f, Mean solar exoatmospheric " \
                "irradiance=%.1f]" % (esd, esun)
            g.message(msg)

            # convert
            tmp_toar = "%s.Reflectance" % tmp  # Spectral Reflectance
            toar = "%s = %f * %s * %f^2 / %f * cos(%f)" \
                % (tmp_toar, math.pi, tmp_rad, esd, esun, sza)
            grass.mapcalc(toar)

            # strings for output's metadata
            history_toar = toar
            history_toar += "ESD=%f; BAND_Esun=%f; SZA=%f" % (esd, esun, sza)
            title_toar = "%s band (Top of Atmosphere Reflectance)" % band
            units_toar = "Unitless planetary reflectance"
            description_toar = "Top of Atmosphere `echo ${BAND}` band spectral"
            " Reflectance (unitless)"

        if tmp_toar:
    
            # history entry
            run("r.support", map=tmp_toar,
                title=title_toar, units=units_toar, description=description_toar,
                source1=source1_toar, source2=source2_toar, history=history_toar)
    
            # add suffix to basename & rename end product
    #        toar_name = ("%s.%s" % (band, outputsuffix))
            toar_name = ("%s.%s" % (band.split('@')[0], outputsuffix))
            run("g.rename", rast=(tmp_toar, toar_name))
    
        elif tmp_rad:
    
            # history entry
            run("r.support", map=tmp_rad,
                title=title_rad, units=units_rad, description=description_rad,
                source1=source1_rad, source2=source2_rad, history=history_rad)
    
            # add suffix to basename & rename end product
    #        rad_name = ("%s.%s" % (band, outputsuffix))
            rad_name = ("%s.%s" % (band.split('@')[0], outputsuffix))
            run("g.rename", rast=(tmp_rad, rad_name))

    # visualising-related information
    if not keep_region:
        grass.del_temp_region()  # restoring previous region settings
    g.message("\n|! Region's resolution restored!")
    g.message("\n>>> Hint: rebalancing colors "
              "(i.colors.enhance) may improve appearance of RGB composites!",
              flags='i')

if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    sys.exit(main())
