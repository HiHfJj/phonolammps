import os
import numpy as np

from phonopy.structure.atoms import PhonopyAtoms
from lammps import lammps


def mass_to_symbol(mass, tolerance=5e-1):
    from phonopy.structure.atoms import atom_data

    for element in atom_data:
        if element[3] is not None and abs(mass - element[3]) < tolerance:
            return element[1]

    return 'H'  # in case no match found use H as wildcard


def get_structure_from_poscar(file_name, number_of_dimensions=3):
    """
    Read crystal structure from a VASP POSCAR type file

    :param file_name: POSCAR filename
    :param number_of_dimensions: number of dimensions of the crystal structure
    :return: Atoms (phonopy) type object containing the crystal structure
    """
    # Check file exists
    if not os.path.isfile(file_name):
        print('Structure file does not exist!')
        exit()

    # Read from VASP POSCAR file
    poscar_file = open(file_name, 'r')
    data_lines = poscar_file.read().split('\n')
    poscar_file.close()

    multiply = float(data_lines[1])
    direct_cell = np.array([data_lines[i].split()
                            for i in range(2, 2+number_of_dimensions)], dtype=float)
    direct_cell *= multiply
    scaled_positions = None
    positions = None

    try:
        number_of_types = np.array(data_lines[3+number_of_dimensions].split(),dtype=int)

        coordinates_type = data_lines[4+number_of_dimensions][0]
        if coordinates_type == 'D' or coordinates_type == 'd' :

            scaled_positions = np.array([data_lines[8+k].split()[0:3]
                                         for k in range(np.sum(number_of_types))],dtype=float)
        else:
            positions = np.array([data_lines[8+k].split()[0:3]
                                  for k in range(np.sum(number_of_types))],dtype=float)

        atomic_types = []
        for i,j in enumerate(data_lines[5].split()):
            atomic_types.append([j]*number_of_types[i])
        atomic_types = [item for sublist in atomic_types for item in sublist]

    # Old style POSCAR format
    except ValueError:
        number_of_types = np.array(data_lines[5].split(), dtype=int)
        coordinates_type = data_lines[6][0]
        if coordinates_type == 'D' or coordinates_type == 'd':
            scaled_positions = np.array([data_lines[7+k].split()[0:3]
                                         for k in range(np.sum(number_of_types))], dtype=float)
        else:
            positions = np.array([data_lines[7+k].split()[0:3]
                                  for k in range(np.sum(number_of_types))], dtype=float)

        atomic_types = []
        for i,j in enumerate(data_lines[0].split()):
            atomic_types.append([j]*number_of_types[i])
        atomic_types = [item for sublist in atomic_types for item in sublist]

    return PhonopyAtoms(symbols=atomic_types,
                        scaled_positions=scaled_positions,
                        cell=direct_cell)


def get_structure_from_lammps(file_name, show_log=False):
    """
    Get the crystal structure from lammps input

    :param file_name: LAMMPS input filename
    :return: numpy array matrix with forces of atoms [Natoms x 3]
    """

    cmd_list = ['-log', 'none']
    if not show_log:
        cmd_list += ['-echo', 'none', '-screen', 'none']

    lmp = lammps(cmdargs=cmd_list)

    lmp.file(file_name)
    lmp.command('run 0')

    na = lmp.get_natoms()

    xlo =lmp.extract_global("boxxlo", 1)
    xhi =lmp.extract_global("boxxhi", 1)
    ylo =lmp.extract_global("boxylo", 1)
    yhi =lmp.extract_global("boxyhi", 1)
    zlo =lmp.extract_global("boxzlo", 1)
    zhi =lmp.extract_global("boxzhi", 1)
    xy =lmp.extract_global("xy", 1)
    yz =lmp.extract_global("yz", 1)
    xz =lmp.extract_global("xz", 1)

    unitcell = np.array([[xhi-xlo, xy,  xz],
                           [0,  yhi-ylo,  yz],
                           [0,   0,  zhi-zlo]]).T

    positions = lmp.gather_atoms("x", 1, 3)
#    type_mass = lmp.gather_atoms("mass", 1, 1)
    type_mass = lmp.extract_atom("mass", 2)

    type = lmp.gather_atoms("type", 0, 1)

    positions = np.array([positions[i] for i in range(na * 3)]).reshape((na, 3))
    masses = np.array([type_mass[type[i]] for i in range(na)])
    symbols = [mass_to_symbol(masses[i]) for i in range(na)]

    return PhonopyAtoms(positions=positions,
                        masses=masses,
                        symbols=symbols,
                        cell=unitcell)

def generate_VASP_structure(structure, scaled=True, supercell=(1, 1, 1)):

    cell = structure.get_cell()
    types = structure.get_chemical_symbols()

    atom_type_unique = np.unique(types, return_index=True)

    # To use unique without sorting
    sort_index = np.argsort(atom_type_unique[1])
    elements = np.array(atom_type_unique[0])[sort_index]
    elements_count= np.diff(np.append(np.array(atom_type_unique[1])[sort_index], [len(types)]))


    vasp_POSCAR = 'Generated using phonoLAMMPS\n'
    vasp_POSCAR += '1.0\n'
    for row in cell:
        vasp_POSCAR += '{0:20.10f} {1:20.10f} {2:20.10f}\n'.format(*row)
    vasp_POSCAR += ' '.join(elements)
    vasp_POSCAR += ' \n'
    vasp_POSCAR += ' '.join([str(i) for i in elements_count])

    if scaled:
        scaled_positions = structure.get_scaled_positions()
        vasp_POSCAR += '\nDirect\n'
        for row in scaled_positions:
            vasp_POSCAR += '{0:15.15f}   {1:15.15f}   {2:15.15f}\n'.format(*row)

    else:
        positions = structure.get_positions()
        vasp_POSCAR += '\nCartesian\n'
        for row in positions:
            vasp_POSCAR += '{0:20.10f} {1:20.10f} {2:20.10f}\n'.format(*row)

    return vasp_POSCAR
