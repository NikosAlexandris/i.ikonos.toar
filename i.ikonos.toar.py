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

# IKONOS Band (λ)                           1st column
# CalCoef(λ) Pre  2/22/01 (DN/(mW/cm2-sr))  2nd column
# CalCoef(λ) Post 2/22/01 (DN/(mW/cm2-sr))  3rd column
# Effective Bandwidthλ (nm)                 4th column
# Esun(λ) (W/m2/μm)                         5th column
"""
CC = {'Pan':   (161, 161, 403.0, 1375.8),  # Note: Pan is "TDI-13"
      'Blue':  (633, 728, 071.3, 1930.9),
      'Green': (649, 727, 088.6, 1854.8),
      'Red':   (840, 949, 065.8, 1556.5),
      'NIR':   (746, 843, 095.4, 1156.9)}

cc_update = datetime(2001, 2, 22)

spectral_bands = CC.keys()


# helper functions ----------------------------------------------------------
def cleanup():
    grass.run_command('g.remove', flags='f', type="rast",
                      pattern='tmp.%s*' % os.getpid(), quiet=True)


def run(cmd, **kwargs):
    """ """
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
    tmp = "tmp." + grass.basename(tmpfile)  # use its basenam

    # -----------------------------------------------------------------------
    # Global Metadata
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

    # loop over all bands
    for band in spectral_bands:

        global tmp_rad

        g.message("|* Processing the %s spectral band" % band)

        if not keep_region:
            g.message("\n|! Matching region to %s" % band)  # set region
            run('g.region', rast=band)   # ## FixMe

        # -----------------------------------------------------------------------
        # Band dependent metadata for Spectral Radiance
        # -----------------------------------------------------------------------

        # Calibration Coefficients
        if acq_dat < cc_update:
            g.message("\n|! Using Pre-2001 Calibration Coefficient values")
            cc = float(CC[band][0])
        else:
            cc = float(CC[band][1])

        # Effective bandwidth
        bw = float(CC[band][2])

        # -------------------------------------------------------------------
        # Converting to Spectral Radiance
        # -------------------------------------------------------------------

        msg = "\n|> Converting to Spectral Radiance: " \
#            "L(λ) = 10^4 x DN(λ) / CalCoef(λ) x Bandwidth(λ)"  # Unicode? ##
        g.message(msg)
        
        msg = "   [Calibration Coefficient=%d, Bandwidth=%.1f]" \
            % (cc, bw)
        g.message(msg)

        tmp_rad = "%s.Radiance" % tmp  # Temporary Map

        rad = "%s = 10^4 * %s / %f * %f" \
            % (tmp_rad, band, cc, bw)
        grass.mapcalc(rad)

        history_rad = rad  # track command

        units = "W / m2 / μm / ster"
        description = "At-sensor %s band spectral Radiance (W/m2/μm/sr)" % band
        source1 = '"IKONOS Planetary Reflectance and '
        'Mean Solar Exoatmospheric Irradiance", by Martin Taylor, Geoeye'
        history_rad += "Calibration Coefficient=%d; Effective Bandwidth=%.1f" \
            % (cc, bw)

        # -------------------------------------------------------------------
        # Converting to Top-of-Atmosphere Reflectance
        # -------------------------------------------------------------------

        if not radiance:

            global tmp_toar
            msg = "\n|> Converting to Top-of-Atmosphere Reflectance" \
#            "ρ(p) = π x L(λ) x d^2 / ESUN(λ) x cos(θ(S))"  # Unicode? ######
            g.message(msg)

            esun = CC[band][3]  # Mean solar exoatmospheric irradiance

            msg = "   [Earth-Sun distane=%f, Mean Band Irradiance=%.1f]" \
                % (esd, esun)
            g.message(msg)

            tmp_toar = "%s.Reflectance" % tmp  # Spectral Reflectance
            toar = "%s = %f * %s * %f^2 / %.1f * cos(%f)" \
                % (tmp_toar, math.pi, tmp_rad, esd, esun, sza)
            grass.mapcalc(toar)

            history_toar = toar  # track command

            # strings for output's metadata
            title = "echo ${BAND} band (Top of Atmosphere Reflectance)"
            units = "Unitless planetary reflectance"
            description = "Top of Atmosphere `echo ${BAND}` band spectral "
            "Reflectance (unitless)"
            source1 = '"IKONOS Planetary Reflectance and Mean Solar '
            'Exoatmospheric Irradiance", by Martin Taylor, Geoeye'
            source2 = "USGS via Digital Globe"
            history_toar += "ESD=%f; BAND_Esun=%f; SZA=%f" % (esd, esun, sza)

    if tmp_toar:
        # history entry
        run("r.support",
            map=tmp_toar, title=title, units=units, description=description,
            source1=source1, source2=source2, history=history_toar)

        # add suffix to basename & rename end product
        toar_name = ("%s.%s" % (tmp_toar.split('@')[0], outputsuffix))
        band_basename = grass.basename(tmp_toar)
        print band_basename
        run("g.rename", rast=(tmp_toar, toar_name))

    elif tmp_rad:
        run("r.support", map=tmp_rad,

            history=history_rad)

#        # history entry
#        run("r.support", map=tmp_rad, history)

        # add suffix to basename & rename end product
#        msx_nam = ("%s.%s" % (msx.split('@')[0], outputsuffix))
        run("g.rename", rast=(tmp_rad, "Rad"))

    # visualising-related information
    if not keep_region:
        grass.del_temp_region()  # restoring previous region settings
    g.message("\n|! Region's resolution restored!")
    g.message("\n>>> Rebalancing colors "
              "(i.colors.enhance) may improve appearance of RGB composites!",
              flags='i')

if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    sys.exit(main())
