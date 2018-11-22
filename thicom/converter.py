#!/usr/bin/python
from __future__ import print_function
from PIL import Image
import numpy as np
import scipy.misc
import dicom
import sys
import os
# Proprietary imports
from thicom.components import find_dcm, find_dcmdir, is_dicom, redirect_to_tqdm, tqdm
from thicom.decomp import Decompressor

if sys.version[0] == '2': input = raw_input


class Converter:

    def __init__(self, dicom_root_path='.', run=False, log_dir=None, verbose=False, cleanup=False, yes_to_all=False,
                 same_name=False):
        """
        This class is meant as a wrapper to python's dicom package and mainly handles converting
        dicom images to .png ones. This was meant as a method for anonymizing those images, so
        the patients', doctors', and hospitals' information are purposely ignored.

        In order to preserve the useful metadata, we coded it into the name of the image:
        The images names' format is: SeriesDescription_InstanceNumber.png.
        For example the 13th image of an axial TIRM (T2 TIRM tra dark-fl)
        will be named t2_tirm_tra_dark-fluid_pat2_13.png

        A log file from the DICOMDIR files is also generated. This contains sensitive information,
        but can be anonymized through a method of the Anonymizer class.

        Python's dicom package is utilized to read the images and convert them to numpy arrays.
        They are then saved as .png images through scipy.

        :param dicom_root_path: A path under which the converter will search for images (string).
        :param run: True/False whether or not to convert on instantiation (bool).
        :param log_dir: Path of the directory in which the log file will be stored in (string).
        :param verbose: True/False whether or not user wants his screen flooded with messages (bool).
        :param cleanup: True/False whether or not the user wants to delete the old dicom files
                        after conversion to .png images (bool).
        :param yes_to_all: True if user wants to bypass all confirmations (bool).
        :param same_name: True if user wants to keep the same name as the original DICOM
                          False if user wants the user to keep the SeriesDescription_InstanceNumber.png
                          (bool)
        """
        curr = os.getcwd()
        self.log = []
        self.dir_path = os.path.abspath(dicom_root_path)
        if log_dir:
            self.log_dir = os.path.abspath(log_dir)
        else:
            self.log_dir = self.dir_path
        self.verbose = verbose
        self.cleanup = cleanup
        self.compressed = []
        self.successful = 0
        self.failed = 0
        self.frames = 0
        self.removed = 0
        self.yes_to_all = yes_to_all
        if run:
            # If single image
            if is_dicom(dicom_root_path):
                # Change directory to save .png in the same location where the DICOM image is.
                os.chdir(os.path.split(dicom_root_path)[0])
                self.to_png(dcm=dicom_root_path, same_name=same_name)
            # If DICOMDIR or dicom root path
            else:
                self.convert_all()
        os.chdir(curr)

    def convert(self, dcm):
        """
        Converts a dicom image as to a numpy.ndarray. If the dicom image is monochrome, it will be
        stored in an (rows,cols) shaped array. If it is in RGB format, the array will be shaped
        (3,rows,cols). If the dicom file contains a series of N images, it renurns an (N,rows,cols)
        shaped array. In other cases it doesn't convert the image and returns None.
        If the image is compressed it returns the string 'compressed'
        :param dcm: A path to a DICOM image (string).
        :return: A numpy.ndarray containing pixel intensity values
                (N,rows,cols) --> if image is monochrome and contains N frames.
                (rows,cols)   --> if image is monochrome.
                (3,rows,cols) --> if image is RGB.
                None          --> if conversion failed.
                'compressed'  --> if image is compressed
        """
        ds = dicom.read_file(dcm)
        # Check for multi-frame images
        try:
            if ds.NumberOfFrames > 1:
                if ds.PhotometricInterpretation == 'MONOCHROME2':
                    dims = (ds.NumberOfFrames, int(ds.Rows), int(ds.Columns))
                    arr = np.zeros(dims, dtype=ds.pixel_array.dtype)
                    arr[:, :, :] = ds.pixel_array
                    return arr
        except NotImplementedError:
            # Pixel data in the image are compressed
            if self.verbose:
                print('DICOM image is in a compressed format, will attempt decompression.')
            return 'compressed'
        except AttributeError:
            pass
        # Check photometric interpretation
        try:
            if ds.PhotometricInterpretation == 'RGB':
                dims = (3, int(ds.Rows), int(ds.Columns))
                arr = np.zeros(dims, dtype=ds.pixel_array.dtype)
                arr[:, :, :] = ds.pixel_array
                arr = arr.reshape((arr.shape[1], arr.shape[2], 3))
            elif ds.PhotometricInterpretation == 'MONOCHROME2':
                dims = (int(ds.Rows), int(ds.Columns))
                arr = np.zeros(dims, dtype=ds.pixel_array.dtype)
                arr[:, :] = ds.pixel_array
            else:
                raise NotImplementedError('Unknown PhotometricInterpretation attribute value: '
                                          '{}'.format(ds.PhotometricInterpretation))
        except NotImplementedError:
            # If image is compressed
            if self.verbose:
                print('DICOM image is in a compressed format, will attempt decompression.')
            return 'compressed'
        except AttributeError:
            print('---- Not a valid image, cannot convert ----')
            return None
        return arr

    def view(self, dcm):
        """
        Shows a dicom image to the screen
        :param dcm: A path to a DICOM image (string).
        """
        arr = self.convert(dcm)
        if arr is None: return
        if isinstance(arr, str):
            if arr == 'compressed':
                if 'dcmp' not in globals():
                    # global object to preserve it in case other images are compressed too
                    global dcmp
                    dcmp = Decompressor(verbose=self.verbose)
                if self.verbose: print('Attempting to decompress image: {}'.format(dcm))
                dcm_dcmp = dcmp.decompress_file(dcm)
                arr = self.convert(dcm_dcmp.replace('\\', ''))
                os.remove(dcm_dcmp)
                if isinstance(arr, str):
                    if arr == 'compressed':
                        print('Failed to decompress image.')
                        return
        # Linearly normalize the image before viewing. PIL accpets only arrays with values under 255.
        arr = self.normalize_image(arr)
        if len(arr.shape) == 3:
            img = Image.fromarray(arr, 'RGB')
        elif len(arr.shape) == 2:
            img = Image.fromarray(arr)
        else:
            print('Invalid array shape: {}'.format(arr.shape))
            return
        img.show()

    def view_many(self, dcm_list, anim=True):
        """
        View many dicom images at once using matplotlib. Two options: view as an animation OR view
        as an array of images.
        :param dcm_list: A list of paths to dicom images (list of strings).
        :param anim: True if user wants images shown as a gif animation,
                     False if user wants array of images (bool).
        """

        # find out how many valid images there are
        valid = []
        # how many are valid DICOM images
        for dcm in dcm_list:
            if is_dicom(dcm):
                valid.append(dcm)
            else:
                if self.verbose:
                    print('{} is not a valid DICOM image, skipping...'.format(dcm))

        # sort by filenames:
        valid.sort()
        arrs = []
        for dcm in valid:
            arr = self.convert(dcm)
            if arr is None: continue
            if isinstance(arr, str):
                if arr == 'compressed':
                    if 'dcmp' not in globals():
                        # global object to preserve it in case other images are compressed too
                        global dcmp
                        dcmp = Decompressor(verbose=self.verbose)
                    if self.verbose: print('Attempting to decompress image: {}'.format(dcm))
                    dcm_dcmp = dcmp.decompress_file(dcm)
                    arr = self.convert(dcm_dcmp.replace('\\', ''))
                    os.remove(dcm_dcmp)
                    if isinstance(arr, str):
                        if arr == 'compressed':
                            print('Failed to decompress image.')
                            continue
            arrs.append(arr)

        # if no valid images found return
        if len(arrs) < 1:
            print('No valid DICOM images!')
            return
        # if 1 valid image found call .view() method
        elif len(arrs) == 1:
            self.view(valid[0])
            return
        else:
            if self.verbose: print('Plotting {} images...'.format(len(valid)))
            # only execute if more than one valid DICOM images are found
            arrs = map(self.normalize_image, arrs)
            import matplotlib.pyplot as plt
            # if user wants to animate the images in a gif
            if anim:
                import matplotlib.animation as animation
                # define figure
                fig = plt.figure()
                im = plt.imshow(arrs[0])

                # define function that produces images
                def updatefig(j):
                    try:
                        im.set_array(arrs[j])
                    except IndexError:
                        return
                    return im,

                # create and show animation
                animation.FuncAnimation(fig, updatefig)
                plt.show()

            else:
                import math
                # figure out how many subplots per line
                dim = math.ceil(math.sqrt(len(arrs)))
                # define figure
                fig = plt.figure()
                # dynamically add subplots to the figure
                for i in range(len(arrs)):
                    fig.add_subplot(dim, dim, i+1)
                    plt.tick_params(axis='both', which='both', bottom='off', top='off', left='off',
                                    labelbottom='off', labeltop='off', labelleft='off', labelright='off')
                    plt.show(block=False)
                    plt.imshow(arrs[i])
                # show
                plt.show()

    @staticmethod
    def normalize_image(arr):
        """
        Linearly normalizes an array.
        :param arr: A numpy array of shape (x,x) or (x,x,3) (np.ndarray).
        :return: A linearly normalized array of the same shape
        """
        arr = arr.astype('float')
        if len(arr.shape) == 2:
            minval = arr.min()
            maxval = arr.max()
            if minval != maxval:
                arr -= minval
                arr *= (255.0/(maxval - minval))
        elif len(arr.shape) == 3:
            for i in range(3):
                minval = arr[..., i].min()
                maxval = arr[..., i].max()
                if minval != maxval:
                    arr[..., i] -= minval
                    arr[..., i] *= (255.0/(maxval-minval))
        return arr

    def to_png(self, dcm, same_name=True):
        """
        Takes a path to a dicom image and converts it to a png image. If the image is compressed,
        it attempts to call the Decompressor class to decompress them. If the image has N frames
        it saves them as N images.
        :param dcm: A path to a dicom image (string)
        :param same_name: True if user wants to keep the same name as the original DICOM
                          False if user wants the user to keep the SeriesDescription_InstanceNumber.png
                          (bool)
        :return: True if all OK, False if conversion fails. (bool)
        """

        # call the converter method to turn the image into a numpy.array
        arr = self.convert(dcm)
        if arr is None: return False

        # if the image is compressed, attempt to decompress it
        if isinstance(arr, str):
            if arr == 'compressed':
                if 'dcmp' not in globals():
                    # global object to preserve it in case other images are compressed too
                    global dcmp
                    dcmp = Decompressor(verbose=self.verbose)
                if self.verbose: print('Attempting to decompress image: {}'.format(dcm))
                dcm_dcmp = dcmp.decompress_file(dcm)
                arr = self.convert(dcm_dcmp.replace('\\', ''))
                # remove decompressed image once we're done
                os.remove(dcm_dcmp.replace('\\', ''))
                if arr == 'compressed':
                    print('Failed to decompress image.')
                    self.compressed.append(dcm)
                    return False
                else:
                    if self.verbose: print('Decompression successful!')

        # figure out the image's name
        ds = dicom.read_file(dcm)
        if not same_name:
            name = '_'.join(ds.SeriesDescription.split()) + '_' + str(ds.InstanceNumber).zfill(3)
            name = name.replace('/', '_')
        else:
            name = dcm[:-4] if dcm[-4:].lower() == '.dcm' else dcm

        # save the array as a png image
        try:
            if ds.NumberOfFrames > 1:
                for i in range(ds.NumberOfFrames):
                    if not same_name:
                        name = '_'.join(ds.SeriesDescription.split())
                        name = '_'.join(name.split('/'))
                        name = name.replace(':', '_')
                    scipy.misc.imsave(name + '_' + str(i+1).zfill(3) + '.png', arr[i, :, :])
                print('Image sequence has {} frames.'.format(ds.NumberOfFrames))
                self.frames += ds.NumberOfFrames - 1
                return True
        except AttributeError:
            # AttributeError --> normal dicom that doesn't have NumberOfFrames attribute
            pass
        try:
            if not same_name:
                c = 0
                while os.path.exists(name + '.png'):
                    original = name
                    c += 1
                    name = name + '_copy' + str(c)
                    name = name.replace(':', '_')

                    if self.verbose:
                        print('Image {} already exists. Attempting to save DICOM as {}.'.format(original, name))
            scipy.misc.imsave(name + '.png', arr)

        except ValueError as v:
            # scipy.imsave error stating that `cmax` should be larger than `cmin`
            # can view the image but scipy can't handle saving it into a .png
            print('ValueError: {} at image {}'.format(v.message, dcm))
            return False
        return True

    def create_log(self, dir_path, write=False):
        """
        Reads a DICOMDIR file and generates a log file according to it. Appends the log to the
        class' log list. Optionally writes it to a file.
        :param dir_path: path of the DICOMDIR file (string).
        :param write: True/False whether or not to write the log to a file (bool).
        :return: True if all OK
        """
        dcm = dicom.read_dicomdir(dir_path)
        dots = '---------'
        space = '          '
        dump = str(dcm).split(dots)
        series_info = []
        ser_count = 0
        patient_info = study_info = ''
        for chunk in dump:
            if 'PATIENT' in chunk:
                patient_info = '\n'.join([dots*4 + ' PATIENT INFO ' + dots*4] + chunk.split('\n')[8:])
            if 'STUDY'in chunk:
                study_info = '\n'.join([dots*4 + ' STUDY INFO ' + dots*4] + chunk.split('\n')[3:])
            if 'SERIES' in chunk:
                ser_count += 1
                ser = '\n'.join([space*2 + dots*2 + ' SERIES ' + str(ser_count) + ' ' + dots*2] +
                                chunk.split('\n')[3:9])
                series_info.append(dots*4 + ' SERIES INFO ' + dots*4 + '\n' + ser)
        self.log.append('\n'.join([patient_info] + [study_info] + series_info) + '\n')
        if write:
            filename = os.path.join(self.log_dir, 'conversion_log.txt')
            with open(filename, 'a') as f:
                f.write('\n')
                f.write(self.log[-1])
                print('Log file created: {}'.format(os.path.abspath(filename)))
        return True

    def convert_all(self, pt=None):
        """
        Searches for DICOMDIR files, generates logs accordingly. These DICOMDIR files correspond to
        patients. User chooses which patients to convert to png files.
        :param pt: Path under which to search
        """
        if not pt:
            pt = self.dir_path

        # path points to a dicomdir file
        if pt.split('/')[-1] == 'DICOMDIR':
            if not os.path.exists(pt):
                raise OSError('Invalid path: {}'.format(pt))
            root_path = '/'.join(pt.split('/')[:-1])
            self.convert_patient(root_path)

        # search for one or more dicomdir under directory
        else:
            dir_lst = find_dcmdir(pts=pt)
            if len(dir_lst) > 1:
                dir_list_w = [x + '/DICOMDIR' for x in dir_lst]
                if not self.yes_to_all:
                    # query user and generate a list of patients
                    print('Printing DICOMDIR locations:')
                    for i in range(len(dir_list_w)):
                        print('{:<5} {}'.format(str(i+1) + '.', dir_list_w[i]))
                    key = input('Which DICOMDIR(s) do you want to convert?\n(1, 2, 3, ... / multiple '
                                'indice separated by a single space / 0 for none / anything else for all)\n')
                    if key.isdigit():
                        if int(key) == 0:
                            print('Exiting')
                            sys.exit()
                        dir_lst = [dir_lst[int(key) - 1]]
                    elif all([x.isdigit() for x in key.split()]) and key != '':
                        dir_lst = [dir_lst[int(i) - 1] for i in key.split()]

            # convert each patient in the list
            for dcmdir in dir_lst:
                self.convert_patient(dcmdir)

            if not dir_lst:
                self.convert_patient(pt, no_dir=True)

        # generate report
        print('\n------------------- Report -------------------')
        if self.compressed:
            print('Compressed image directories:')
            print('Storing a list of those files in:\n{}'.format(os.path.join(self.log_dir, 'compressed images.txt')))
            comp_dir = set([os.path.split(x) for x in self.compressed])
            for cm in comp_dir:
                print(cm)
            if self.compressed:
                with open(self.log_dir + '/compressed images.txt', 'wb') as f:
                    f.write('DICOM images that failed due to compression:')
                    for d in self.compressed:
                        f.write(d)
        print('{:<40} {}'.format('DICOM-to-png conversions attempted:', self.successful + self.failed))
        print('{:<40} {}'.format('DICOM-to-png conversions successful:', self.successful))
        print('{:<40} {}'.format('DICOM-to-png conversions failed:', self.failed))
        print('{:<40} {}'.format('Total number of .png images created:', self.successful + self.frames))
        if self.cleanup:
            print('{:<40} {}'.format('Deleted DICOM images:', self.removed))
        print()

    def convert_patient(self, root_path, no_dir=False):
        """
        Converts all images from a single patient. Also generates the log file. Optionally
        deletes all existing DICOM images after conversion.
        :param root_path: A path to a patient's directory (string).
        :param no_dir: True if patient has no DICOMDIR (bool).
        """
        # Search for dicom images
        print('Attempting to convert patient {}.'.format(os.path.relpath(root_path)))
        os.chdir(root_path)
        if self.verbose:
            print("Searching for DICOM images under directory\n{}".format(os.path.abspath(root_path)))
        dcm_lst = find_dcm(pts=root_path)
        if not len(dcm_lst):
            raise ValueError('Path does not contain any DICOM files.')

        # Create log file
        if not no_dir:
            print('Creating log:')
            self.create_log(root_path + '/DICOMDIR', write=True)

        # Query user
        if not self.yes_to_all:
            if self.cleanup:
                keyword = 'will delete'
            else:
                keyword = 'without deleting'
            check = input("Proceeding will convert all DICOM to '.png' images ({} the originals). "
                          "Do you want to proceed? (Y/N)  ".format(keyword))
            if check.lower().replace(' ', '') in ('yy', 'yestoall', 'yes_to_all'):
                self.yes_to_all = True
            if check.lower() not in ('y', 'yes', 'proceed', '') and not self.yes_to_all:
                return
        c = 0

        # Convert each image to png
        with redirect_to_tqdm() as stdout:
            for dcm in tqdm(dcm_lst, file=stdout, dynamic_ncols=True, desc='Converting images'):
                flg = self.to_png(dcm, same_name=False)
                if flg:
                    c += 1
        # Report
        print('Done!')
        print('Successfully converted {} of {} total images.'.format(c, len(dcm_lst)))
        if c < len(dcm_lst):
            print('Failed to convert {} of {} total images.'.format(len(dcm_lst) - c, len(dcm_lst)))
        self.successful += c
        self.failed += len(dcm_lst) - c

        # Cleanup patient
        if self.cleanup:
            print('Cleanup procedure initiated.')
            if not self.yes_to_all:
                check = input("Proceeding will delete all DICOM images. Do you want to proceed? (Y/N)  ")
                if check.lower().replace(' ', '') in ('yy', 'yestoall', 'yestocleanup', 'yestoclean'):
                    self.yes_to_all = True
                if check.lower() not in ('y', 'yes', 'proceed', '') and not self.yes_to_all:
                    return
            if self.yes_to_all:
                # search again in the case of decompressed images being generated (issue in previous version)
                dcm_lst = find_dcm(pts=root_path)
                c = 0
                with redirect_to_tqdm() as stdout:
                    for dcm in tqdm(dcm_lst, file=stdout, dynamic_ncols=True, desc='Deleting images:'):
                        os.remove(dcm)
                        c += 1
                self.removed += c
                print('Done!')
                print('Successfully deleted {} of {} total images.'.format(c, len(dcm_lst)))

    def generate_logs(self, pt=None, clean_previous=False, write=False):
        """
        Searches for DICOMCIR files and then generates logs according to each one
        :param pt: path under which to search for DICOMDIR files (string).
        :param clean_previous: True/False whether or not to delete class' log variable (bool).
        :param write: True/False whether or not to write the log to a file (bool).
        :return: True if all OK
        """
        if not pt: pt = self.log_dir
        dir_lst = find_dcmdir(pts=pt)
        if clean_previous: self.log = []
        for d in dir_lst:
            self.create_log(d + '/DICOMDIR')
        if write:
            if not os.path.isdir(self.log_dir):
                os.mkdir(self.log_dir)
            filename = os.path.join(self.log_dir, 'conversion_log.txt')
            with open(filename, 'wb') as f:
                c, ln = 1, len(self.log)
                for log in self.log:
                    if self.verbose: print('Writing log {} of {}'.format(c, ln))
                    f.write(log)
                    f.write('\n\n')
                    c += 1
            print('Successfully wrote {} log files in {}'.format(ln, filename))
        return True

    def get_results(self):
        """
        Method used for retrieving conversion stats for logging or summarization purposes.
        :return: Number of png images generated and number of images it failed to convert (int, int).
        """
        return self.successful + self.frames, self.failed


if __name__ == '__main__':
    assert len(sys.argv) == 2, "Too many arguments. Enter just one argument." if len(
        sys.argv) > 1 else "Too few arguments. DICOM root path required as an argument."
    dcm_dir = sys.argv[1]
    assert os.path.exists(dcm_dir), "The path you entered is not valid."
    conv = Converter(dicom_root_path=dcm_dir, run=True, verbose=False)
