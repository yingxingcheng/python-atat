#!/usr/bin/env python
'''
python script to submit atat jobs to the queue

usage:
In a directory with a str.out file, run this script.

To use it on many files, use this command:

foreachfile -e -d 3 wait run_atat_vasp.py
Execute the specified command in every first-level subdirectory containing the file filename.
The -e option cause foreachfile to skip directories containing the file "error".
The -d option specifies to go down to lower level subdirectories as well (the default is 1).
'''
import os, shutil, sys
from subprocess import Popen, PIPE
from ase.calculators.vasp import *
import ase.io

def run_atat_vasp():
    # We need to create a customized vasp.wrap file
    if os.path.exists('vasp.wrap'):
        pass
    elif os.path.exists('../vasp.wrap'):
        shutil.copy('../vasp.wrap','vasp.wrap')
    elif os.path.exists('../../vasp.wrap'):
        shutil.copy('../../vasp.wrap','vasp.wrap')
    else:
        raise Exception, 'no vasp.wrap found in ../vasp.wrap or ../../vasp.wrap'

    #Now we create the vasp input files so we can compute the number
    #of bands we want
    os.system('str2ezvasp') # creates vasp.in
    os.system('ezvasp -n vasp.in') # creates VASP input files

    # now we have a minimal setup we can read into ase, compute the
    # nbands we want.

    atoms = ase.io.read('POSCAR')

    calc = Vasp()
    de = calc.get_default_number_of_electrons()

    # de is a list of tuples (symbol, nvalence) [('Fe',10.00),('Ni',8.00)]
    # convert to a dictionary to make it easy to add them up.
    default_electrons = {}
    for sym,n in de:
        default_electrons[sym] = n

    NELEC = 0
    for atom in atoms:
        NELEC += default_electrons[sym]

    NIONS = len(atoms)

    # make sure there are always at least 8 bands for one atom, with
    # one valence electron, you can get 3 bands with this, which is
    # not enough.
    NBANDS = max(8, NELEC*0.65 + 2*NIONS)

    # removes VASP input files because they will be regenerated by
    # runstruct_vasp
    os.system('cleanvasp')

    f = open('vasp.wrap','r')
    lines = f.readlines()
    f.close()
    # now we need to modify vasp.in so that runstruct will create the
    # right INCAR with NBANDS in it.
    lines.insert(1,'NBANDS = %i\n' % int(NBANDS))

    # Now we check if magnetic moments should be added in.
    magnetic_species = {'Fe':2.5,
                        'Ni':2}

    magnetic = False
    magmoms = []
    for atom in atoms:
        if atom.symbol in magnetic_species:
            magnetic = True
            magmoms.append(magnetic_species[atom.symbol])
        else:
            magmoms.append(0)

    if magnetic:
        lines.append('MAGMOM = %s\n' % ' '.join([str(x) for x in magmoms]))
        lines.append('ISPIND = 2\n')
        lines.append('ISPIN = 2\n')

    f = open('vasp.wrap','w')
    f.writelines(lines)
    f.close()

    os.system('str2ezvasp') # remake vasp.in

    # Now submit the job.

    script = '''
    #!/bin/bash
    cd $PBS_O_WORKDIR
    rm -f error           # remove these if they are hanging around
    rm -f energy
    rm -f wait            # we are about to start, so remove wait
    runstruct_vasp -p
    rm -f jobid           # after job is over, remove jobid file
    # end
    '''

    if os.path.exists('jobid'):
        print 'jobid file exists in %s. Exiting' % os.getcwd()
        sys.exit()

    # submit a job to the queue
    p = Popen(['qsub',
               '-joe',
               '-N',
               "%s" % os.getcwd(),
               '-l walltime=168:00:00'],
               stdin=PIPE, stdout=PIPE, stderr=PIPE)

    out, err = p.communicate(script)
    f = open('jobid','w')
    f.write(out)
    f.close()
    print '|[[shell:qstat -f %s][%s]]|' % (out.strip(),out.strip())

if __name__ == '__main__':

    from optparse import OptionParser

    parser = OptionParser()

    (options, args) = parser.parse_args()
    CWD = os.getcwd()

    if len(args) > 0:
        for arg in args:
            try:
                os.chdir(arg)
                run_atat_vasp()
            finally:
                os.chdir(CWD)
    else:
        run_atat_vasp()
