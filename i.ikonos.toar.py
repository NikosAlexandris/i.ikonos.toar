# -*- coding: utf-8 -*-
"""
@author: Nikos Alexandris | Created on Sat Nov  8 00:05:17 2014
"""

# librairies
import math
import grass.script as grass
from grass.pygrass.modules.shortcuts import general as g


# Constants

# Band Parameters # Table extracted using Okular! # -------------------------

# IKONOS Band (λ)								1st column
# CalCoef λ Pre 2/22/01* (DN/(mW/cm2-sr))		2nd column
# CalCoef λ  Post 2/22/01* (DN/(mW/cm2-sr))	3rd column
# Bandwidthλ (nm)								4th column
# Esunλ (W/m2/μm)								5th column

# Band	 CCPre	 CCPost BW		Esun # Note: Pan is (TDI-13) ### ------------|
CC = {'Pan':   (161, 161, 403.0, 1375.8),
      'Blue':  (633, 728, 071.3, 1930.9),
      'Green': (649, 727, 088.6, 1854.8),
      'Red':   (840, 949, 065.8, 1556.5),
      'NIR':   (746, 843, 095.4, 1156.9)}

# MetaData
# Day of Year for the image under processing is "166"
DOY = 166 # HardCoded ! ------------------------------------------------<<<
ESD = 1.0157675 # HardCoded ! ------------------------------------------<<<

# Esun: 		Mean solar exoatmospheric irradiance(s) (W/m2/μm), interpolated
# pre-defined (above)

# cos(θ_s):	cosine of Solar Zenith Angle, where:
# θ_s  or  SZA is the Solar Zenith Angle
# SEA is the Solar Elevation Angle, retrieved from the image's metadata
SEA = 52.78880
SZA = 90 - SEA
BAND_Esun = CC[band][3]
msg = "Using Esun=%" % esun


      
# Bands
spectral_bands = "Pan Blue Green Red NIR"
msg = "Spectral bands to be processed: "
"%s -- Change this msg!" % spectral_bands
g.message(msg)


# helper functions ----------------------------------------------------------
def cleanup():
    grass.run_command('g.remove', flags='f', type="rast",
                      pattern='tmp.%s*' % os.getpid(), quiet=True)


def run(cmd, **kwargs):
    """ """
    grass.run_command(cmd, quiet=True, **kwargs)


def main():
    # loop over all bands
    for band in spectral_bands:

        g.message("Processing the %s spectral band" % band)

        # set region
        run('g.region', rast=band)   ### FixMe
        # echo something?
        
        # set band parameters as variables
        cc = CC[band][1]
        bw = CC[band][2]
        msg = "Band Parameters: Calibration Coefficient=%f, Bandwidth=%f" \
        % (cc, bw)
        g.message(msg)
        

        # conversion to Radiance --------------------------------------------
        """
        Spectral Radiance for spectral band λ at the sensor’s aperture
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

        msg = "Conversion to Radiance: "
        "L(λ) = 10^4 • DN(λ) / CalCoef(λ) • Bandwidth(λ)"
        g.message(msg)

        rad = "%s = 10**4 * %s / %f * %f" % (rad, dn, cc, bw)
        grass.mapcalc(rad)

        # add info
        cmd_history = rad

        run("r.support", map=band_rad,
            units="W / m2 / μm / ster",
            description="At-sensor %s band spectral Radiance (W/m2/μm/sr)" \
            % band,
            source1='"IKONOS Planetary Reflectance and '
            'Mean Solar Exoatmospheric Irradiance", by Martin Taylor, Geoeye',
            history=cmd_history)

        # conversion to ToAR ------------------------------------------------
        """
        Calculate Planetary Reflectance:

        ρ_p = π • L_λ • d^2 / ESUN_λ • cos(θ_S)

        ρ: Unitless Planetary Reflectance
       To be calculated

        π: mathematical constant
        L_λ: from equation (1)

        d: Earth-Sun distance in astronomical units, interpolated value
        from <http://landsathandbook.gsfc.nasa.gov/excel_docs/d.xls>
        """

        msg = "Conversion to Top-of-Atmosphere Reflectance: "
        "ρ(p) = π • L(λ) • d^2 / ESUN(λ) • cos(θ(S))"
        g.message(msg)

        toar = "%s = math.pi * rad * %f**2 / %f * cos(%f)" \
            % (toar, band_rad, esd, esun, sza)

        # add some metadata
        run('r.support',
            map=band_toar,
            title="echo ${BAND} band (Top of Atmosphere Reflectance)",
            units="Unitless planetary reflectance",
            description="Top of Atmosphere `echo ${BAND}` band spectral "
            "Reflectance (unitless)",
            source1='"IKONOS Planetary Reflectance and Mean Solar '
            'Exoatmospheric Irradiance", by Martin Taylor, Geoeye',
            source2="USGS via Digital Globe",
            history="ESD=%f; BAND_Esun=%f; SZA=%f" % (esd, esun, sza))
