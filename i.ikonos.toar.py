#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@author: Nikos Alexandris | Created on Sat Nov  8 00:05:17 2014
"""

#%Module
#%  description: Converting IKONOS digital numbers (radiometrically corrected) to Top-of-Atmosphere Spectral Radiance or Reflectance  (Krause, 2005)
#%  keywords: imagery, radiometric conversion, radiance, reflectance, IKONOS
#%End

#%flag
#%  key: r
#%  description: Convert to at-sensor spectral radiance
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
#% required: no
#%end

#%option
#% key: doy
#% type: integer
#% description: Aquisition's Day of Year
#% options: 1-365
#% guisection: Metadata
#% required: no
#%end

#%option
#% key: sea
#% key_desc: angle (degrees)
#% type: double
#% description: Aquisition's Sun Elevation Angle
#% options: 0.0 - 90.0
#% guisection: Metadata
#% required: no
#%end


# librairies
import os
import sys
import atexit

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
Band Parameters (Taylor, 2005)

# IKONOS Band (λ)                           1st column
# CalCoef(λ) Pre  2/22/01* (DN/(mW/cm2-sr)) 2nd column
# CalCoef(λ) Post 2/22/01* (DN/(mW/cm2-sr)) 3rd column
# Effective Bandwidthλ (nm)                 4th column
# Esun(λ) (W/m2/μm)                         5th column
"""

CC = {'Pan':   (161, 161, 403.0, 1375.8),  # Note: Pan is "TDI-13"
      'Blue':  (633, 728, 071.3, 1930.9),
      'Green': (649, 727, 088.6, 1854.8),
      'Red':   (840, 949, 065.8, 1556.5),
      'NIR':   (746, 843, 095.4, 1156.9)}

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

    mapset = grass.gisenv()['MAPSET']  # Current Mapset?

    imglst = [spectral_bands]
#    images = {}
#    for img in imglst:  # Retrieving Image Info
#        images[img] = Info(img, mapset)
#        images[img].read()

    grass.use_temp_region()  # to safely modify the region

    # ========================================== Temporary files ========
    tmpfile = grass.tempfile()  # Temporary file - replace with os.getpid?
    tmp = "tmp." + grass.basename(tmpfile)  # use its basenam
    # Temporary files ===================================================

    # -----------------------------------------------------------------------
    # Required Metadata
    # -----------------------------------------------------------------------

    if utc:
        acq_tim = AcquisitionTime(utc)  # will hold esd (earth-sun distance)
        esd = acq_tim.esd  # Earth-Sun distance
    elif doy:
        esd = jd_to_esd(int(doy))
    else:
        grass.fatal(_("Either the UTC string or "
                      "the Day-of-Year (doy) are required!"))

    # Sun Zenith Angle based on Sun Elevation Angle
    sza = 90 - float(sea)

    # loop over all bands
    for band in spectral_bands:
        global tmp_rad

        g.message("Processing the %s spectral band" % band)

        g.message("|  Matching region to %s" % band)  # set region
        run('g.region', rast=band)   # ## FixMe

        cc = float(CC[band][1])  # calibration coefficient
        bw = float(CC[band][2])  # effective bandwidth
        msg = "Band Parameters: Calibration Coefficient=%f, Bandwidth=%f" \
            % (cc, bw)
        g.message(msg)

        # conversion to Radiance --------------------------------------------
        """Spectral Radiance for spectral band λ at the sensor’s aperture
        in: watts / (meter squared * ster * µm)

        L_λ = 10^4 • DN_λ / CalCoef_λ • Bandwidth_λ    (1)
        where:
        - CalCoef_λ = Radiometric calibration coefficient [DN/(mW/cm 2- sr)]
        - Bandwidth_λ = Bandwidth of spectral band λ (nm)

        Alt. unit(s) notation: (W/m2/μm/sr) || W / m^2 * ster * micro-m

        Source: "IKONOS Planetary Reflectance and Mean Solar Exoatmospheric
        Irradiance", by Martin Taylor, Geoeye

        See also: <http://landsat.usgs.gov/how_is_radiance_calculated.php>

        Related entry in Wikipedia, <http://en.wikipedia.org/wiki/Radiance>:
        "The SI unit of radiance is watts per steradian per square metre
        (W·sr−1·m−2)"
        """

#        msg = "Conversion to Radiance: " \
#            "L(λ) = 10^4 x DN(λ) / CalCoef(λ) x Bandwidth(λ)"
#        g.message(msg)

        tmp_rad = "%s.Radiance" % tmp  # Spectral Radiance

        rad = "%s = 10^4 * %s / %f * %f" \
            % (tmp_rad, band, cc, bw)
        grass.mapcalc(rad)


        history_rad = rad  # track command

        # conversion to ToAR ------------------------------------------------
        if not radiance:
            global tmp_toar
            """Calculate Planetary Reflectance:
            ρ(p) = π x L(λ) x d^2 / ESUN(λ) x cos(θ(S))
            - ρ: Unitless Planetary Reflectance [To be calculated]
            - π: Mathematical constant
            - L_λ: Spectral Radiance from equation (1)
            - d: Earth-Sun distance in astronomical units [calculated using
            AcquisitionTime class]
            """
            msg = "Conversion to Top-of-Atmosphere Reflectance: "
            "ρ(p) = π x L(λ) x d^2 / ESUN(λ) x cos(θ(S))"
            g.message(msg)

            esun = CC[band][3]  # Mean solar exoatmospheric irradiance
            msg = "Parameters: Earth-Sun distane=%f, Mean Band Irradiance=%f" \
                % (esd, esun)
            g.message(msg)

            tmp_toar = "%s.Reflectance" % tmp  # Spectral Reflectance
            toar = "%s = %f * %s * %f^2 / %f * cos(%f)" \
                % (tmp_toar, math.pi, tmp_rad, esd, esun, sza)
            grass.mapcalc(toar)

            history_toar = toar  # track command

            # add some metadata
            title = "echo ${BAND} band (Top of Atmosphere Reflectance)"
            units = "Unitless planetary reflectance"
            description = "Top of Atmosphere `echo ${BAND}` band spectral "
            "Reflectance (unitless)"
            source1 = '"IKONOS Planetary Reflectance and Mean Solar '
            'Exoatmospheric Irradiance", by Martin Taylor, Geoeye'
            source2 = "USGS via Digital Globe"
            history_toar += "ESD=%f; BAND_Esun=%f; SZA=%f" % (esd, esun, sza)

#            history_ref = "%s, %s, %s, %s, %s, %s" % \
#                (title, units, description, source1, source2, toar_history)

    if tmp_toar:
        # history entry
#        run("r.support", map=tmp_ref, history_ref)

        # add suffix to basename & rename end product
#        msx_nam = ("%s.%s" % (msx.split('@')[0], outputsuffix))
        run("g.rename", rast=(tmp_toar, "Ref"))

    elif tmp_rad:
        run("r.support", map=tmp_rad,
            units="W / m2 / μm / ster",
            description="At-sensor %s band spectral Radiance (W/m2/μm/sr)"
            % band,
            source1='"IKONOS Planetary Reflectance and '
            'Mean Solar Exoatmospheric Irradiance", by Martin Taylor, Geoeye',
            history=history_rad)

#        # history entry
#        run("r.support", map=tmp_rad, history)

        # add suffix to basename & rename end product
#        msx_nam = ("%s.%s" % (msx.split('@')[0], outputsuffix))
        run("g.rename", rast=(tmp_rad, "Rad"))

    # visualising-related information
    grass.del_temp_region()  # restoring previous region settings
    g.message("\n|! Region's resolution restored!")
    g.message("\n>>> Rebalancing colors "
              "(i.colors.enhance) may improve appearance of RGB composites!",
              flags='i')

if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    sys.exit(main())
