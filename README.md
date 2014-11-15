`i.ikonos.toar` is a GRASS-GIS add-on module converting IKONOS DN values (Digital Numbers, that is relatively readiometrically corrected detector data) to Spectral Radiance or Reflectance.

_Conversion to top-of-atmosphere spectral radiance is a simple two step process that involves multiplying
radiometrically corrected image pixels by the appropriate absolute radiometric calibration factor (also referred to as a K factor) to get band-integrated radiance [W-m-2-sr-1] and then dividing the result by the appropriate effective bandwidth to get spectral radiance [W-m-2-sr-1-μm-1]._ (Taylor, 2005)

For the moment, the module requires as an input the acquisition's date and time formatted as a UTC string and the (mean) Sun Elevation Angle. Thoese are required to calculate the Earth-Sun distance parameter for the modules' internal computations and can be retrieved from the imagery's metadata files. The UTC string can be overriden by using the optional parameter `doy`, given the day of year (Julian Day) has been correctly estimated for the acquisition that is to be processed.

Optionally, the module may operate on the current computational region, instead of a bands whole extent.

*ToAdd: More details about retrieving the acquisition's metada.*

Source: Taylor, 2005



## Spectral Radiance

for spectral band λ at the sensor’s aperture in
watts / (meter squared * ster * µm)

L(λ) = 10^4 x DN(λ) / CalCoef(λ) x Bandwidth(λ) (1)

where:
- CalCoef_λ = Radiometric calibration coefficient [DN/(mW/cm 2- sr)]
- Bandwidth_λ = Bandwidth of spectral band λ (nm)

Alt. unit(s) notation:
- (W/m2/μm/sr)
- W / m^2 * ster * micro-m
- W·sr−1·m−2 | "The SI unit of radiance is watts per steradian
per square metre" <http://en.wikipedia.org/wiki/Radiance>

## Planetary Reflectance

ρ(p) = π x L(λ) x d^2 / ESUN(λ) x cos(θ(S))

where:
- ρ: Unitless Planetary Reflectance
- π: Mathematical constant
- L(λ): Spectral Radiance from equation (1)
- d: Earth-Sun distance in astronomical units [calculated using
AcquisitionTime class]

# Sources
- "IKONOS Planetary Reflectance and Mean Solar
Exoatmospheric Irradiance", by Martin Taylor, 2005. Geoeye.
- <http://landsat.usgs.gov/how_is_radiance_calculated.php>
