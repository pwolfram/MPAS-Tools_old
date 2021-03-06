#!/usr/bin/env python
# Script to create a grid with land ice variables from an MPAS grid.
# I've only tested it with a periodic_hex grid, but it should work with any MPAS grid.
# Currently variable attributes are not copied (and periodic_hex does not assign any, so this is ok).  If variable attributes are added to periodic_hex, this script should be modified to copy them (looping over dir(var), skipping over variable function names "assignValue", "getValue", "typecode").

import sys, numpy
from netCDF4 import Dataset
from optparse import OptionParser


sphere_radius = 6.37122e6 # earth radius, if needed

print "** Gathering information.  (Invoke with --help for more details. All arguments are optional)"
parser = OptionParser()
parser.add_option("-i", "--in", dest="fileinName", help="input filename.  Defaults to 'grid.nc'", metavar="FILENAME")
parser.add_option("-o", "--out", dest="fileoutName", help="output filename.  Defaults to 'landice_grid.nc'", metavar="FILENAME")
parser.add_option("-l", "--level", dest="levels", help="Number of vertical levels to use in the output file.  Defaults to the number in the input file", metavar="FILENAME")
parser.add_option("--beta", dest="beta", action="store_true", help="Use this flag to include the field 'beta' in the resulting file.")
parser.add_option("--diri", dest="dirichlet", action="store_true", help="Use this flag to include the fields 'dirichletVelocityMask', 'uReconstructX', 'uReconstructY' needed for specifying Dirichlet velocity boundary conditions in the resulting file.")
options, args = parser.parse_args()

if not options.fileinName:
    print "No input filename specified, so using 'grid.nc'."
    options.fileinName = 'grid.nc'
if not options.fileoutName:
    print "No output filename specified, so using 'landice_grid.nc'."
    options.fileoutName = 'landice_grid.nc'
print '' # make a space in stdout before further output

# Get the input file
filein = Dataset(options.fileinName,'r')

# Define the new file to be output 
fileout = Dataset(options.fileoutName,"w",format=filein.file_format)

# ============================================
# Copy over all the dimensions to the new file
# ============================================
# Note: looping over dimensions seems to result in them being written in seemingly random order.
#       I don't think this matters but it is not aesthetically pleasing.
#       It may be better to list them explicitly as I do for the grid variables, 
#       but this way ensures they all get included and is easier.
# Note: The UNLIMITED time dimension will return a dimension value of None with Scientific.IO.  This is what is supposed to happen.  See below for how to deal with assigning values to a variable with a unlimited dimension.  Special handling is needed with the netCDF module.
for dim in filein.dimensions.keys():
    if dim == 'nTracers': 
        pass  # Do nothing - we don't want this dimension 
    else:    # Copy over all other dimensions
      if dim == 'Time':      
         dimvalue = None  # netCDF4 won't properly get this with the command below (you need to use the isunlimited method)
      elif (dim == 'nVertLevels'): 
        if options.levels is None:
          # If nVertLevels is in the input file, and a value for it was not
          # specified on the command line, then use the value from the file (do nothing here)
          print "Using nVertLevels from the intput file:", len(filein.dimensions[dim])
          dimvalue = len(filein.dimensions[dim])
        else:
          # if nVertLevels is in the input file, but a value WAS specified
          # on the command line, then use the command line value
          print "Using nVertLevels specified on the command line:", int(options.levels)
          dimvalue = int(options.levels)
      else:
         dimvalue = len(filein.dimensions[dim])
      fileout.createDimension(dim, dimvalue)
# There may be input files that do not have nVertLevels specified, in which case
# it has not been added to the output file yet.  Treat those here.
if 'nVertLevels' not in fileout.dimensions:
   if options.levels is None:
       print "nVertLevels not in input file and not specified.  Using default value of 10."
       fileout.createDimension('nVertLevels', 10)
   else:
       print "Using nVertLevels specified on the command line:", int(options.levels)
       fileout.createDimension('nVertLevels', int(options.levels))
# Also create the nVertInterfaces dimension, even if none of the variables require it.
fileout.createDimension('nVertInterfaces', len(fileout.dimensions['nVertLevels']) + 1)  # nVertInterfaces = nVertLevels + 1
print 'Added new dimension nVertInterfaces to output file with value of ' + str(len(fileout.dimensions['nVertInterfaces'])) + '.'

# Create the dimensions needed for time-dependent forcings
# Note: These have been disabled in the fresh implementation of the landice core.  MH 9/19/13
#fileout.createDimension('nBetaTimeSlices', 1)
#fileout.createDimension('nSfcMassBalTimeSlices', 1)
#fileout.createDimension('nSfcAirTempTimeSlices', 1)
#fileout.createDimension('nBasalHeatFluxTimeSlices', 1)
#fileout.createDimension('nMarineBasalMassBalTimeSlices', 1)

print 'Finished creating dimensions in output file.\n' # include an extra blank line here

# ============================================
# Copy over all of the required grid variables to the new file
# ============================================
vars2copy = ('latCell', 'lonCell', 'xCell', 'yCell', 'zCell', 'indexToCellID', 'latEdge', 'lonEdge', 'xEdge', 'yEdge', 'zEdge', 'indexToEdgeID', 'latVertex', 'lonVertex', 'xVertex', 'yVertex', 'zVertex', 'indexToVertexID', 'cellsOnEdge', 'nEdgesOnCell', 'nEdgesOnEdge', 'edgesOnCell', 'edgesOnEdge', 'weightsOnEdge', 'dvEdge', 'dcEdge', 'angleEdge', 'areaCell', 'areaTriangle', 'cellsOnCell', 'verticesOnCell', 'verticesOnEdge', 'edgesOnVertex', 'cellsOnVertex', 'kiteAreasOnVertex')
for varname in vars2copy:
   thevar = filein.variables[varname]
   datatype = thevar.dtype
   newVar = fileout.createVariable(varname, datatype, thevar.dimensions)
   if filein.on_a_sphere == "YES             ":
     if varname in ('xCell', 'yCell', 'zCell', 'xEdge', 'yEdge', 'zEdge', 'xVertex', 'yVertex', 'zVertex', 'dvEdge', 'dcEdge'):
       newVar[:] = thevar[:] * sphere_radius / filein.sphere_radius
     elif varname in ('areaCell', 'areaTriangle', 'kiteAreasOnVertex'):
       newVar[:] = thevar[:] * (sphere_radius / filein.sphere_radius)**2
     else:
       newVar[:] = thevar[:]
   else: # not on a sphere
     newVar[:] = thevar[:]

# ============================================
# Create the land ice variables (all the shallow water vars in the input file can be ignored)
# ============================================
nVertLevels = len(fileout.dimensions['nVertLevels'])
datatype = filein.variables['xCell'].dtype  # Get the datatype for double precision float
datatypeInt = filein.variables['indexToCellID'].dtype  # Get the datatype for integers
#  Note: it may be necessary to make sure the Time dimension has size 1, rather than the 0 it defaults to.  For now, letting it be 0 which seems to be fine.
layerThicknessFractions = fileout.createVariable('layerThicknessFractions', datatype, ('nVertLevels', ))
layerThicknessFractions[:] = numpy.zeros(layerThicknessFractions.shape)
# Assign default values to layerThicknessFractions.  By default they will be uniform fractions.  Users can modify them in a subsequent step, but doing this here ensures the most likely values are already assigned. (Useful for e.g. setting up Greenland where the state variables are copied over but the grid variables are not modified.)

# uniform layer fractions (default)
layerThicknessFractions[:] = 1.0 / nVertLevels

# explictly specify layer fractions
#layerThicknessFractions[:] = [0.1663,0.1516,0.1368,0.1221,0.1074,0.0926,0.0779,0.0632,0.0484,0.0337]

# With Scientific.IO.netCDF, entries are appended along the unlimited dimension one at a time by assigning to a slice.
# Therefore we need to assign to time level 0, and what we need to assign is a zeros array that is the shape of the new variable, exluding the time dimension!
newvar = fileout.createVariable('thickness', datatype, ('Time', 'nCells'))
newvar[0,:] = numpy.zeros( newvar.shape[1:] )
newvar = fileout.createVariable('temperature', datatype, ('Time', 'nCells', 'nVertLevels'))
newvar[0,:,:] = numpy.zeros( newvar.shape[1:] )
# These landice variables are stored in the mesh currently, and therefore do not have a time dimension.
#    It may make sense to eventually move them to state.
newvar = fileout.createVariable('bedTopography', datatype, ('nCells',))
newvar[:] = numpy.zeros(newvar.shape)
newvar = fileout.createVariable('sfcMassBal', datatype, ('nCells',))
newvar[:] = numpy.zeros(newvar.shape)
print 'Added default variables: thickness, temperature, bedTopography, sfcMassBal'

if options.beta:
   newvar = fileout.createVariable('beta', datatype, ('nCells',))
   newvar[:] = 1.0e8  # Give a default beta that won't have much sliding.
   print 'Added optional variable: beta'

if options.dirichlet:
   newvar = fileout.createVariable('dirichletVelocityMask', datatypeInt, ('Time', 'nCells', 'nVertInterfaces'))
   newvar[:] = 0  # default: no Dirichlet b.c.
   newvar = fileout.createVariable('uReconstructX', datatype, ('Time', 'nCells', 'nVertInterfaces',))
   newvar[:] = 0.0
   newvar = fileout.createVariable('uReconstructY', datatype, ('Time', 'nCells', 'nVertInterfaces',))
   newvar[:] = 0.0
   print 'Added optional variables: dirichletVelocityMask, uReconstructX, uReconstructY'

# These boundary conditions are currently part of mesh, and are time independent.  If they change, make sure to adjust the dimensions here and in Registry.
# Note: These have been disabled in the fresh implementation of the landice core.  MH 9/19/13
#newvar = fileout.createVariable('betaTimeSeries', datatype, ( 'nCells', 'nBetaTimeSlices', ))
#newvar[:] = numpy.zeros(newvar.shape)
#newvar = fileout.createVariable('sfcMassBalTimeSeries', datatype, ( 'nCells', 'nSfcMassBalTimeSlices', ))
#newvar[:] = numpy.zeros(newvar.shape)
#newvar = fileout.createVariable('sfcAirTempTimeSeries', datatype, ( 'nCells', 'nSfcAirTempTimeSlices', ))
#newvar[:] = numpy.zeros(newvar.shape)
#newvar = fileout.createVariable('basalHeatFluxTimeSeries', datatype, ( 'nCells', 'nBasalHeatFluxTimeSlices',))
#newvar[:] = numpy.zeros(newvar.shape)
#newvar = fileout.createVariable('marineBasalMassBalTimeSeries', datatype, ( 'nCells', 'nMarineBasalMassBalTimeSlices',))
#newvar[:] = numpy.zeros(newvar.shape)

print 'Finished creating variables in output file.\n' # include an extra blank line here

# ============================================
# Copy over all of the netcdf global attributes
# ============================================
print "---- Copying global attributes from input file to output file ----"
for name in filein.ncattrs():
  # sphere radius needs to be set to that of the earth if on a sphere
  if name == 'sphere_radius' and getattr(filein, 'on_a_sphere') == "YES             ":
    setattr(fileout, 'sphere_radius', sphere_radius)
    print 'Set global attribute   sphere_radius = ', str(sphere_radius)
  else:
    # Otherwise simply copy the attr
    setattr(fileout, name, getattr(filein, name) )
    print 'Copied global attribute  ', name, '=', getattr(filein, name)


filein.close()
fileout.close()

print '\n** Successfully created ' + options.fileoutName + '.**'
