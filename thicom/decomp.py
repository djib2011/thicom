from __future__ import print_function
import sys
import os
# Proprietary imports
from thicom.components import find_dcm, suppress_stdout

if sys.version[0] == '2': input = raw_input


class Decompressor:

    def __init__(self, pt='.', run=False, replace=False, mod='_decomp', verbose=False):
        """
        The Decompressor class handles compressed DICOM images. Most of these are compressed
        through lossless-JPEG compression and can't be handled by python's dicom package.
        This class is meant to serve as a script that decompresses them in order to be accessible
        through python.
        In order to perform the decompression linux's "gdcmconv" tool will be used.
        More info: http://gdcm.sourceforge.net/wiki/index.php/Main_Page
        This script requires a linux operating system with the above tool installed.
        :param pt: A directory under which the class looks for dicom images (string).
        :param run: True/False whether or not to begin decompression upon instantiation (bool).
        :param replace: True/False whether or not to replace compressed images with decompressed ones (bool).
        :param mod: A string that will be placed at the end of the name of the decompressed images.
                    Will be taken into account only if replace is False (string).
        :param verbose: True/False whether or not user wants his screen flooded with messages (bool).
        """

        self.verbose = verbose

        # Check for requirements
        if self.verbose: print('Checking for requirements...')
        required = self.check_gdcmconv()
        if not required: sys.exit()

        self.replace = replace
        self.mod = mod

        # Initiate decompression
        if run:
            # find all dicom images under given path
            dicom_list = find_dcm(pts=pt, verbose=self.verbose)

            # if the program  found any valid dicom images:
            if len(dicom_list) > 0:
                # user confirmation
                keywords = 'will replace' if replace else 'without deleting'
                check = input("Proceeding will convert the specified DICOM to '.png' image(s), "
                              "{} the original(s). Do you want to proceed? (Y/N)  ".format(keywords))
                if check.lower() not in ('y', 'yes', 'proceed', ''): return

                # decompress them
                self.decompression(dicom_list)
                print('Completed decompression!')

    @staticmethod
    def check_gdcmconv():
        """
        Checks if the OS is compatible and the gdcmconv tool is installed. Both are required
        to run this script.
        :return: True if the requirements are met.
                 False if not. (bool)
        """
        import subprocess
        # Check if user is using linux OS
        if 'linux' not in sys.platform.lower():
            print('This functionality is only supported for linux operating systems.')
            return False
        # Check if gdmconv is installed
        try:
            # can't mute annoying gdcmconv output :P
            with suppress_stdout():
                subprocess.call(['gdcmconv', '-v'], stdout=None, stderr=None)
        except OSError:
            print('In order to proceed with the decompression, install GDCM.\n'
                  'Info: http://gdcm.sourceforge.net/wiki/index.php/Main_Page')
            return False
        return True

    def decompression(self, lst):
        """
        Tales a list of paths and attempts to decomrpess them.
        :param lst: List of paths to compressed dicom images (list of strings)
        :return: True if it decompressed at least one image.
                 False otherwise. (bool)
        """
        if not isinstance(lst, list):
            raise TypeError('Argument must be a list!')
        c = 0
        for f in lst:
            if os.path.exists(f):
                try:
                    self.decompress_file(f)
                    c += 1
                    print('Decompressed image {} of {}.'.format(c, len(lst)))
                except TypeError:
                    # no actual error here, will work on uncompressed images too
                    print('Cannot decompress image {}'.format(f))
                    print('Image possibly not compressed.')
            else:
                print('Invalid path {}, will skip to next.'.format(f))
        if len(lst) > 1:
            print('Successfully decompressed {} of {} images.'.format(c, len(lst)))
        return True if c > 0 else False

    def decompress_file(self, f, name=None, mod=None):
        """
        Decompresses a single DICOM image using linux's gdcmconv tool.
        :param f: Path of the compressed dicom file (string).
        :param name: Name that it will receive after decompression.
                    If replace is True this will be ignored (string).
        :param mod: If no name is selected, a modifier string can be chosen. This will add the modifier
                    at the end of the decompressed image's new name (string).
        :return: Returns the path of the new image (string).
        """

        # make path UNIX-style (with \ before spaces)
        f = '\\ '.join(f.replace('\\ ', ' ').split())
        # determine the new name
        if not mod: mod = self.mod
        if self.replace: name = f
        else:
            if not name:
                fn = f
                if f[-4:] == '.dcm':
                    fn = f[:-4]
                name = fn + mod + '.dcm'

        # printing
        if self.verbose:
            print('Decompressing compressed DICOM image: {}'.format(f))
            if self.replace:
                print('Will replace existing...')
            else:
                print('Saving new image as: {}'.format(name))

        # generate linux command
        command = 'gdcmconv --raw {} {}'.format(f, name)
        if self.verbose: print(command)

        # mute annoying gdcmconv output and run command
        with suppress_stdout():
            os.system(command)

        return name

    @staticmethod
    def decompress_all(lst, names=None, replace=False):
        """
        This function takes a list of compressed DICOM images and decompresses them, using linux's gdcmconv tool.
        We will be using linux's gdcmconv tool to do the decompression, instructions here:
        http://gdcm.sourceforge.net/html/gdcmconv.html
        :param lst: a list of the dicom files we want to decompress (list).
        :param names: a list of the names the files end up with (list).
        :param replace: True if we want the decompressed files to overwrite the compressed ones (bool).
        """
        if not names: names = []
        # Check if first two arguments are lists
        if not isinstance(lst, list) and not isinstance(names, list):
            raise TypeError('Argument must be a list!')
        # If we want to replace the names
        if replace:
            for i in lst:
                # create the command that will decompress each image:
                command = 'gdcmconv --raw {} {}'.format(i, i)
                # run the command:
                os.system(command)
        # If we want to create new names
        else:
            if names:
                # check if the two lists have the same length
                if len(lst) == len(names):
                    raise ValueError('The two lists must have identical length')
            else:
                # if empty list then create every file ending with '_decmp.dcm'
                names = [os.path.split(x)[0] + os.path.split(x)[1]+'_decmp.dcm' for x in lst]

            for i in range(len(lst)):
                # create the command that will decompress each image:
                command = 'gdcmconv --raw {} {}'.format(lst[i], names[i])
                # run the command:
                os.system(command)

    @staticmethod
    def modifier(lst, mod):
        """
        Modifies names in lst accoding to mod
        e.g if mod='_new'
        /path/to/file       -->  /path/to/file_new.dcm
        /path/to/file.dcm   -->  /path/to/file_new.dcm
        :param lst: list of paths
        :param mod: modifier (string)
        :return: list of modified paths
        """
        if not isinstance(lst, list):
            raise TypeError('Argument must be a list!')
        names = []
        # remove '.dcm' from mod if there is one
        if str(mod).find('.dcm') > 0:
            mod = str(mod).split('.')[:-1]
        for pt in lst:
            p, name = os.path.split(pt)  # split into path and file name
            # if there is a dot in the file name
            if name.find('.') > 0:  # if there is a dot in the file name
                # remove suffix and replace it with mod.dcm
                name = ''.join(name.split('.')[:-1]) + str(mod) + '.' + name.split('.')[-1]
            else:  # if there is no .dcm we'll add it ourselves
                name = name + str(mod) + '.dcm'
            names.append(os.path.join(p, name))  # join the path with the name
        return names
