"""
thicom --> thanos' dicom package

Simple manipulation of DICOM images. Wrapper to python's pydicom package.

In order to get the best results please follow the suggested directory structure:
    patients
        |__patient1
        |     |__DICOMDIR
        |     |__random_dicom_folder1
        |     |         |__compressed_image1.dcm
        |     |         |__compressed_image2.dcm
        |     |         |__        ...
        |     |__random_dicom_folder2
        |     |         |__compressed_imageN.dcm
        |     |         |__        ...
        |     |__ ...
        |
        |__patient2
        |     |__DICOMDIR
        |     |__random_dicom_folder
        |     |         |__random_dicom_subfolder1
        |     |         |           |__image1.dcm
        |     |         |           |__   ...
        |     |         |__random_dicom_subfolder2
        |     |         |           |__   ...
        |     |         |__        ...
        |     |__       ...
        |__  ...

-------------------------------------------------------------------------
                            Quick Start
-------------------------------------------------------------------------

Import this package:

        >>> import thicom

        >>> dcm = 'path/to/dicom/image.dcm'
        >>> pt = 'path/to/patients/parent/directory/'

1. To view a DICOM image dcm:
        >>> thicom.view(dcm)

2. To view all DICOM images in the CWD as an animation:
        >>> thicom.view()

3. To decompress compressed all DICOM images under path 'pt':
        >>> pt = 'images/dicom/'
        >>> thicom.decompress(pt)

4. To convert all DICOM images under path 'pt' to .png:
        >>> thicom.to_png(pt)

5. To anonymize all patients under path 'pt':
        >>> thicom.anonymize(pt)

6. To search for DICOM images, DICOMDIR or both under path 'pt':
        >>> thicom.find_dcm(pt)  # looks for dicom images
        >>> thicom.find_dcmdir(pt) # looks for DICOMDIR
        >>> thicom.find_all(pt) # looks for all DICOM files
        >>> thicom.find_png(pt) # looks for png images

7. To check if files are in DICOM format:
        >>> f = 'files/random_file'
        >>> thicom.is_dicom(f)

        >>> files = ['files/random_file1', 'files/random_file2', 'files/random_file3']
        >>> thicom.is_dicom(files)
        Will return True if all files are in DICOM format
        >>> thicom.is_dicom(files, same_size=True)
        Will return a list with the same size as files (e.g. [True, True, False])

By default all functions use the CWD as their default argument.
"""

from __future__ import print_function, absolute_import, division
from thicom import components


def view(dcm=None, animation=True):
    """
    View one or more DICOM images. If an image is compressed it will attempt to generate a temporary decompressed
    copy of the image which it will then delete. This requires a Linux OS with gdcmconv tool installed. Multiple
    images can either be viewed as a gif animation or as an array of images. If there is a DICOMDIR in the path
    then it searches for all images DICOM under it.
    Use:
    1. View single image:
        >>> import thicom
        >>> dcm = 'path/to/dicom/image.dcm'
        >>> thicom.view(dcm)
    2. View list of images as an animation:
        >>> dcm_list = ['path/to/dicom/image1.dcm', 'path/to/dicom/image2.dcm', 'path/to/dicom/image3.dcm']
        >>> thicom.view(dcm_list)
    3. View list of images as an array:
        >>> thicom.view(dcm_list, animation=False)
    4. View all images in CWD:
        >>> thicom.view()
    :param dcm: A path to a dicom image (string).
    :param animation: True if user wants multiple images viewed as an animation,
                      False if he wants them viewed as an array (bool).
    """

    import os
    if not dcm:
        dcm = [x for x in os.listdir('.') if not os.path.isdir(x)]
    from thicom.components import is_dicom
    from thicom.converter import Converter
    conv = Converter()
    if len(dcm) == 1:
        dcm = dcm[0]
    # If string --> single image --> show image
    if isinstance(dcm, str):
        if is_dicom(dcm):
            conv.view(dcm)
            return
        elif os.path.split(dcm)[1] == 'DICOMDIR':
            from thicom.components import find_dcm
            dcm = find_dcm(os.path.abspath(os.path.split(dcm)[0]))
        else:
            print('Not a valid DICOM file!')
            return
    # If iterable --> multiple images
    try:
        if len(dcm) > 1:
            for e in dcm:
                if 'DICOMDIR' in e:
                    from thicom.components import find_dcm
                    dcm = find_dcm(os.path.abspath(os.path.split(e)[0]))
            conv.view_many(dcm_list=dcm, anim=animation)
    except TypeError:
        print('Invalid argument type. This function requires string or iterable.')
        return


def decompress(pt='.', replace=False, mod='_decomp', verbose=False):
    """
    Main function that handles compressed dicom images. Calls Decompressor class from thicom.decomp.
    Requires Linux OS and gdcmconv tool installed!
    Use cases:
    1. Simple decompression of an image with path pt='images/dicom/mydicom.dcm':
        >>> import thicom
        >>> pt = 'images/dicom/mydicom.dcm'
        >>> thicom.decompress(pt)
        This will result in two files under 'images/dicom/':
        a. Compressed 'mydicom.dcm' file.
        b. Decompressed 'mydicom_decomp.dcm' file.
    2. Simple decompression of all dicom images under pt='images/dicom/':
        >>> pt = 'images/dicom/'
        >>> thicom.decompress(pt)
        Each compressed file will have a matching decompressed one with the modifier '_decomp'
        before it's suffix (like in case 2).
        Compressed: mydicom1.dcm, mydicom2.dcm, ...
        Decompressed: mydicom1_decomp.dcm, mydicom2_decomp.dcm, ...
    3. Decompression like before, but with custom modifier mod='_new':
        >>> thicom.decompress(pt, mod='_new')
        Similar to before:
        Compressed: mydicom1.dcm, mydicom2.dcm, ...
        Decompressed: mydicom1_new.dcm, mydicom2_new.dcm, ...
    4. Decompression + Replace:
        >>> thicom.decompress(pt, replace=True)
        This will rewrite the compressed images with the decompressed ones!
        Before: mydicom1.dcm, mydicom2.dcm   <-- These are compressed
        After: mydicom1.dcm, mydicom2.dcm   <-- These are  not compressed
    :param pt: A path under which Decompressor will search for dicom images (string).
    :param replace: True if user wants old compressed dicom deleted,
                    False if user wants both compressed and decompressed images (bool).
    :param mod: A modifier to be added before the suffix of each image if replace is False (string).
    :param verbose: True/False whether or not user wants his screen flooded with messages (bool).
    """

    from thicom.decomp import Decompressor
    Decompressor(pt=pt, run=True, replace=replace, mod=mod, verbose=verbose)


def to_png(dicom_root_path='.', log_dir=None, verbose=False, cleanup=False):
    """
    Main function that handles dicom image conversions. Calls Converter class from thicom.converter.
    Requires numpy for manipulation, scipy for saving. If the image is compressed it will attempt to
    decompress it first using thicom.decomp (requires Linux OS with gdcmconv tool). If the DICOM image
    containes multiple frames, a png image will be generated for each one.
    For best results in multi-patient conversion, directories should be structured as follows:
    patients
        |__patient1
        |     |__DICOMDIR
        |     |__random_dicom_folder1
        |     |         |__compressed_image1.dcm
        |     |         |__compressed_image2.dcm
        |     |         |__        ...
        |     |__random_dicom_folder2
        |     |         |__compressed_imageN.dcm
        |     |         |__        ...
        |     |__ ...
        |
        |__patient2
        |     |__DICOMDIR
        |     |__random_dicom_folder
        |     |         |__random_dicom_subfolder1
        |     |         |           |__image1.dcm
        |     |         |           |__   ...
        |     |         |__random_dicom_subfolder2
        |     |         |           |__   ...
        |     |         |__        ...
        |     |__       ...
        |__  ...
    The focus points of the structure are:
    a. Each patient should have a folder corresponding to him (they don't have to be directly under the
        parent directory.
    b. One DICOMDIR per patient (and per folder).
    c. Any other substructure will be ignored, png images will be dumped in corresponding patient's folder

    Converter Class' PNG naming convention:
    SeriesDescription_InstanceNumber.png, where SeriesDescription is the description of the MRI sequence
    (e.g VsT1W_3D_TFE+GD SENSE) and InstanceNumber is the number of the current image in the series (e.g 13).

    Use cases:
        >>> import thicom
    1. Simple conversion of a dicom image to a .png with path pt='images/dicom/mydicom.dcm':
        >>> pt = 'images/dicom/mydicom.dcm'
        >>> thicom.to_png(pt)
        This will create a .png image in the same directory as pt, named according to the Converter
        class' naming convention.
        No log files of any sort will be generated.
    2. Conversion of a patient's MRI scans to .png images. Path to the patient's directory (that
        contains a DICOMDIR inside) is given as the argument pt='images/dicom/patient1/':
        >>> pt =' images/dicom/patient1/'
        >>> thicom.to_png(pt)
        This will yield the following:
        a. A conversion_log.txt generated from the DICOMDIR file, in path pt.
        b. A series of .png images created from the DICOM ones, in path pt.
        All DICOM files (including the DICOMDIR) remain as they were.
    3. Conversion of DICOM images from multiple patients under path pt='images/dicom/patients'
        >>> pt = 'images/dicom/patients'
        >>> thicom.to_png(pt)
        The following actions will take place:
        - The program will search for DICOMDIR files, assuming that one file corresponds to one patient
        - User will be prompted to select which patients he wants to convert
        - For each patient he selects:
            - A log file will be generated/appended with info from his DICOMDIR. This log is stored in pt.
            - Program will search for DICOM images under the DICOMDIR's directory
            - Each image will be converted to a .png image with a name according to the naming convention
            - These images will all be stored in the patient's directory. Any substructure will be ignored
        Multi-framed DICOM images will be stored as multiple .png files.
        Compressed images will be temporarily decompressed.
    4. Same conversion as before, with cleanup.
        >>> thicom.to_png(pt, cleanup=True)
        This yields the same results as before but removes all DICOM images after they are converted.
        Subdirectories and DICOMDIR files are left intact.
        Sample report from a successful conversion + cleanup procedure:
        ------------------ Report ------------------
        DICOM-to-png conversions attempted:      20
        DICOM-to-png conversions successful:     20
        DICOM-to-png conversions failed:         0
        Total number of .png images created:     20
        Deleted DICOM images:                    20

    :param dicom_root_path: Path under which the program looks for images (string).
    :param log_dir: Path that the log will be stored, by default dicom_root_path (string).
    :param verbose: True/False whether or not user wants his screen flooded with messages (bool).
    :param cleanup: True if user wants DICOM images removed after cleanup (bool).
    """

    from thicom.converter import Converter
    Converter(dicom_root_path=dicom_root_path, run=True, log_dir=log_dir,
              verbose=verbose, cleanup=cleanup)


def anonymize(paths=None, diction=None, verbose=False, similarity_check=False, log=True, log_dir='./logs'):
    """
    Main function used for anonymizing DICOM images. Calls Anonymizer class from thicom.anonymizer.
    Requires pickle for loading/saving and difflib.SequenceMatcher if user want's to run a string
    compare check before patient renames.
    For best results in multi-patient conversion, directories should be structured as follows:
    patients
        |__patient1
        |     |__DICOMDIR
        |     |__random_dicom_folder1
        |     |         |__compressed_image1.dcm
        |     |         |__compressed_image2.dcm
        |     |         |__        ...
        |     |__random_dicom_folder2
        |     |         |__compressed_imageN.dcm
        |     |         |__        ...
        |     |__ ...
        |
        |__patient2
        |     |__DICOMDIR
        |     |__random_dicom_folder
        |     |         |__random_dicom_subfolder1
        |     |         |           |__image1.dcm
        |     |         |           |__   ...
        |     |         |__random_dicom_subfolder2
        |     |         |           |__   ...
        |     |         |__        ...
        |     |__       ...
        |__  ...
    The focus points of the structure are:
    a. Each patient should have a folder corresponding to him, directly under the parent directory
    b. One folder per patient.

    The function doesn't support Single-Patient anonymization

    Use cases:
        >>> import thicom
    1. Anonymization of a single DICOM image pt='images/dicom/mydicom.dcm':
        >>> pt = 'images/dicom/mydicom.dcm'
        >>> thicom.anonymize(pt)
        This will result in a simple change of the PatientName attribute of the dicom image.
        import dicom
        Before: dicom.read_file(pt).PatientName  <--- Thanos
        After: dicom.read_file(pt).PatientName <--- anonymous
    2. Multi-patient anonymization under path pt='patients' (structured as seen above):
        >>> pt = 'patients'
        >>> thicom.anonymize(pt)
        This will fisrty create an anonymization dictionary that maps real patient names to generated
        aliases. Will proceed to anonymize each dicom image under pt according to the mappings. Finally
        will rename the patient directories to match the naming scheme.
        Will store the dictionary to a pickle object and generate log files with the mappings.
        Images will be renamed from mydicom.dcm to mydicom_anon.dcm.
        The procedure WILL replace the originals.
    3. Load previous anonymization dictionary stored in dict_pt='anon/anonymizer_dictionary.pkl':
        >>> dict_pt = 'anon/anonymizer_dictionary.pkl'
        >>> thicom.anonymize(pt, diction=dict_pt)

    :param paths: Path or list of paths. Each path should contain directories corresponding to each
                  patient. ONLY patient dirs and ONE directory per patient (string/list of strings).
    :param diction: OrderedDict or a path to a stored OrderedDict containing patient-alias mappings.
    :param verbose: True/False whether or not user wants his screen flooded with messages (bool).
    :param similarity_check: True if user wants string compare check before anonymization (bool).
    :param log: True/False whether or not to keep a log (bool).
    :param log_dir: Path for the directory where the logs are to be stored (string).
    """

    from thicom.anonymizer import Anonymizer
    Anonymizer(paths=paths, diction=diction, verbose=verbose, similarity_check=similarity_check,
               run=True, log=log, log_dir=log_dir)


def preprocess_mri(parent_dirs='.', verbose=False, diction=None, log_dir='./logs', force=False, check=True):
    """
    Main function that handles all preprocessing operations for MRI images. Briefly this function calls the Anonymizer
    to deliver and apply an anonymization scheme, calls the Converter class to convert all DICOM images to png (while
    generating all necessary log files), then structures the directories neatly and removes all irrelevant files.
    Finally, it searches for all MRI images containing 'T1' in their name and stores them in a separate location.

    Use case:
    >>> import thicom
    >>> pt = 'parent_directory'

    The parent directory should be structured as follows:

    parent_directory
        |__positive
        |     |__patient1
        |     |     |__DICOMDIR
        |     |     |__random_dicom_folder1
        |     |     |         |__compressed_image1.dcm
        |     |     |         |__compressed_image2.dcm
        |     |__patient2
        |     |__  ...
        |
        |__negative
              |__patient3
              |__patient4
              |__  ...

    >>> thicom.preprocess_mri()

    This will result in a following structure:

        parent_directory
        |__positive
        |     |__subject1
        |     |     |__1.MRI
        |     |     |    |__SeriesDescription_InstanceNumber.png
        |     |     |    |__SeriesDescription_InstanceNumber.png
        |     |__subject2
        |     |__  ...
        |
        |__negative
        |     |__subject3
        |     |__subject4
        |     |__  ...
        |__logs
        |     |__anonymizer_dictionary.pkl
        |     |__conversion_log_anon.txt
        |     |__patient aliases.txt
        |     |__patient log.txt
        |     |__      ...
        |__selection
              |__positive
              |     |__MRI
              |          |__T1_MRI_1.png
              |          |__T1_MRI_2.png
              |          |__    ...
              |__negative
                    |__MRI
                         |__T1_MRI_1.png
                         |__T1_MRI_2.png
                         |__    ...

    :param parent_dirs: Path to where the process should start. This path should contain two directories one with
                        positive and one with negative patient directories. Each directory should have the
                        structure mentioned above (str).
    :param verbose: True/False whether or not user wants his screen flooded with messages (bool).
    :param diction: OrderedDict or a path to a stored OrderedDict containing patient-alias mappings.
    :param log_dir: Path for the directory where the logs are to be stored (string).
    :param force: True if user wants to bypass all confirmations (bool).
    :param check: True if user wants to run pre_check before preprocess (bool).
    """
    from thicom.preprocess import Preprocessor
    Preprocessor(parent_dirs=parent_dirs, verbose=verbose, diction=diction, log_dir=log_dir, run=True,
                 pre_check=check, yes_to_all=force)


def force_preprocess_mri(parent_dirs='.', verbose=False, diction=None, log_dir='./logs', check=True):
    """
    Main function that handles all preprocessing operations for MRI images. Briefly this function calls the Anonymizer
    to deliver and apply an anonymization scheme, calls the Converter class to convert all DICOM images to png (while
    generating all necessary log files), then structures the directories neatly and removes all irrelevant files.
    Finally, it searches for all MRI images containing 'T1' in their name and stores them in a separate location.

    Calls thicom.preprocess_mri() with force=True

    Use case:
    >>> import thicom
    >>> pt = 'parent_directory'

    The parent directory should be structured as follows:

    parent_directory
        |__positive
        |     |__patient1
        |     |     |__DICOMDIR
        |     |     |__random_dicom_folder1
        |     |     |         |__compressed_image1.dcm
        |     |     |         |__compressed_image2.dcm
        |     |__patient2
        |     |__  ...
        |
        |__negative
              |__patient3
              |__patient4
              |__  ...

    >>> thicom.force_preprocess_mri()

    This will result in a following structure:

        parent_directory
        |__positive
        |     |__subject1
        |     |     |__1.MRI
        |     |     |    |__SeriesDescription_InstanceNumber.png
        |     |     |    |__SeriesDescription_InstanceNumber.png
        |     |__subject2
        |     |__  ...
        |
        |__negative
        |     |__subject3
        |     |__subject4
        |     |__  ...
        |__logs
        |     |__anonymizer_dictionary.pkl
        |     |__conversion_log_anon.txt
        |     |__patient aliases.txt
        |     |__patient log.txt
        |     |__      ...
        |__selection
              |__positive
              |     |__MRI
              |          |__T1_MRI_1.png
              |          |__T1_MRI_2.png
              |          |__    ...
              |__negative
                    |__MRI
                         |__T1_MRI_1.png
                         |__T1_MRI_2.png
                         |__    ...

    :param parent_dirs: Path to where the process should start. This path should contain two directories one with
                        positive and one with negative patient directories. Each directory should have the
                        structure mentioned above (str).
    :param verbose: True/False whether or not user wants his screen flooded with messages (bool).
    :param diction: OrderedDict or a path to a stored OrderedDict containing patient-alias mappings.
    :param log_dir: Path for the directory where the logs are to be stored (string).
    :param check: True if user wants to run pre_check before preprocess (bool).
    """
    preprocess_mri(parent_dirs=parent_dirs, verbose=verbose, diction=diction, log_dir=log_dir, force=True, check=check)


def pre_check(parent_dirs='.', verbose=False, fix=False):
    """
    Preliminary check for one DICOMDIR-per-patient condition. Also checks if directory name and structure are
    appropriate. Patient directories should be named "D[0-9]. Lastname Firstname" and the DICOMDIR file should
    be located directly under the patient's directory.

    Specifically it checks for:
    1. Patients with DaT scans in DICOM format (with a DICOMDIR).
    2. Patients without MRI DICOMDIRs.
    3. Multiple MRI DICOMDIRS for a single patient.
    4. Wrong directory structure (e.g NPD/Patient/MRI/DICOMDIR instead of NPD/Patient/DICOMDIR)
    5. Wrong directory name (D.Patient, D1 Patient, D1a Patient, etc)

    :param parent_dirs: Path to directory or list of directories each containing NPD/PD subdirectories (str/list of str)
    :param verbose: True/False whether or not user wants his screen flooded with messages (bool).
    :return: True if we have one DICOMDIR per patient, False otherwise (bool).
    :param fix: True if user wants most of the issues to be fixed (bool).
    """
    from thicom.preprocess import Preprocessor
    pre = Preprocessor(parent_dirs=parent_dirs, verbose=verbose, pre_check=not fix)
    if fix:
        result = pre.pre_check(action=fix)
        if result: print('All issues fixed!')


def create_dataset(parent_dir='.', verbose=False, window=3, ratio=0.75):
    """
    Primary function for generating a training and test set from a series of Dat scan and MRI images.

    First all MRIs and Dat scans are gathered, separately for positive and negative patients. MRIs from different
    patients are separated by '-------------'. Then a sliding window technique is applied to the MRIs as shown in the
    following example (for a window size of 3):

    Before the application of the window:
    MRIs = [1.png, 2.png, 3.png, 4.png, 5.png, 6.png, '-------------', 11.png, 12.png, 13.png, 14.png]
    After the application of the window:
    [1.png, 2.png, 3.png, 4.png, 2.png, 3.png, 4.png, 3.png, 4.png, 5.png, 4.png, 5.png, 6.png, 11.png, 12.png, 13.png,
    12.png, 13.png, 14.png]

    Note that windows do overlap but NOT over separate patients!

    After applying the window to the MRIs, each of those windows is combined to a different Dat scan. All possible
    combinations are generated; positive and negative patients are NOT mixed together.

    Finally the data is split into a training and test set according to a given ratio and shuffled through numpy.random.

    Use case:
    >>> import thicom
    >>> pt = 'path/to/dataset/directory'
    >>> thicom.create_dataset(pt)
    # creates two files in pt, one for all the training examples and one for the testing ones.

    :param parent_dir: Path showing where to start the search from (str).
    :param verbose: True/False whether or not user wants his screen flooded with messages (bool).
    :param window: Size of the window to be applied to the MRIs (int).
    :param ratio: training examples / (training + testing) examples (float).
    """
    from thicom.augment import Combine
    Combine(parent_dir=parent_dir, window=window, ratio=ratio, verbose=verbose, save=True)


def is_dicom(dcm, same_size=False):
    """
    Function that checks if a file is a DICOM image. Can also check an iterable of paths to files
    for the same thing. Uses python's magic library. Raises an OSError if dcm is an invalid path.

    >>> import thicom
    >>> dcm = 'images/dicom/mydicom.dcm'
    >>> thicom.is_dicom(dcm)
    True
    >>> dcm_list = ['images/dicom/mydicom1.dcm', 'images/dicom/mydicom2.dcm', 'images/dicom/DICOMDIR']
    >>> thicom.is_dicom(dcm_list)
    False
    >>> thicom.is_dicom(dcm_list, same_size=True)
    [True, True, False]

    :param dcm: A path or iterable containing paths (string/iterable).
    :param same_size: True if dcm is iterable and we want a list returned that specifies which paths
                      are and which aren't dicom images.
                      False if we want it to return a single value based on whether or not ALL elements
                      are DICOM images.
                      (bool)
    :return: True if dcm is a DICOM image.
             False if not. (bool)
             If dcm is an iterable and same_size=True it returns a list of which elements are
             DICOM images and which aren't.
             e.g  [True, True, False, None, True] --> first, second and fifth element are DICOM images
                                                      third is not a DICOM image
                                                      fourth is an invalid path
             If same_size=False returns True if ALL elements are valid images False otherwise (bool).
    """

    return components.is_dicom(dcm=dcm, same_size=same_size)


def find_dcm(pts='.', verbose=False):
    """
    Returns a list of all DICOM images under a certain directory or list of directories.
    Excludes DICOMDIR files from the search. This Function utilizes os.walk and python's magic
    package.
    Use cases:
    >>> import thicom
    >>> dcm = 'images/dicom/'
    >>> thicom.find_dcm()
    ['images/dicom/mydicom1.dcm', 'images/dicom/mydicom2.dcm']

    :param pts: Path to a directory under which the module will search (string),
                or a list of such paths (list of strings).
    :param verbose: True to print each directory it's looking in (bool).
    :return: A list of paths to dicom images - excluding DICOMDIR files (list of strings).
    """

    from thicom import components
    return components.find_dcm(pts=pts, verbose=verbose)


def find_dcmdir(pts='.', verbose=False):
    """
    Returns a list of the directories in which DICOMDIR files are located.
    Use cases:
    >>> import thicom
    >>> dcm = 'images/dicom/'
    >>> thicom.find_dcmdir()
    ['patients/patient1', 'patients/patient2']

    :param pts: Path to a directory under which the module will search (string),
                or a list of such paths (list of strings).
    :param verbose: True to print each directory it's looking in (bool).
    :return: A list of paths to dierctories where DICOMDIR files are stored (list of strings).
             DOES NOT RETURN PATHS TO THE DICOMDIRs THEMSELVES!
    """

    return components.find_dcmdir(pts=pts, verbose=verbose)


def find_all(pts='.', verbose=False):
    """
    This function searches and returns all DICOM files from a given path (or list of paths).
    Use case:
    >>> import thicom
    >>> thicom.find_all()
    ['images/dicom/mydicom1.dcm', 'images/dicom/mydicom2.dcm'], ['images/dicom/DICOMDIR']

    :param pts: A path or a list of paths (string/list of strings)
    :param verbose: True to print each directory it's looking in and the images it found (bool).
    :return: Two lists with the absolute paths of the dicom images and dicomdir files respectively.
             (list, list)
    """

    return components.find_all(pts=pts, verbose=verbose)


def find_png(pts='.', verbose=False, contains=None):
    """
    This function searches and finds all png files under a certain path. If 'contains' is specified, it filters the
    results so that they contain the string. The filtering procedure is NOT case sensitive.

    Use cases:
    1. Search for all png images under the current directory:
    >>> import thicom
    >>> thicom.find_png()
    ['images/mri/img_t1_1.png', 'images/mri/img_T1_2.png', 'images/mri/img_t2_1.png', 'images/mri/img_T2_.png']

    2. Search for all png images under path pt='images/mri' containing the string 't1':
    >>> pt = 'images/mri'
    >>> thicom.find_png(pt, contains='t1')
    ['images/mri/img_t1_1.png', 'images/mri/img_T1_2.png']

    :param pts: A path or a list of paths (string/list of strings).
    :param verbose: True to print each directory it's looking in and the images it found (bool).
    :param contains: A string to filter the results by (str).
    :return: A list of paths to png images (list of strings).
    """
    return components.find_png(pts=pts, verbose=verbose, contains=contains)


def only_png(pts='.'):
    """
    Simple function that checks if all files in a directory are png images.

    Examples:
    >>> import thicom
    >>> import os

    1. Directory contains only png images:
    >>> os.listdir('.')
    ['1.png', '2.png', '3.png']
    >>> thicom.only_png()
    3 files in folder, all png images

    2. Directory doesn't exclusively contain pngs:
    >>> os.listdir('.')
    ['1.png', '2.png', '3.png', '4.txt']
    >>> thicom.only_png()
    4 files in folder but only 3 pngs.

    :param pts: A path of a directory to check if all it's contents are png images (str).
    :return: True if directory contains only png images, False otherwise (bool).
    """
    import os
    contents = os.listdir('.')
    pngs = components.find_png(pts=pts)
    if len(contents) != len(pngs):
        print('{} files in folder but only {} pngs.'.format(len(contents), len(pngs)))
        return False
    else:
        print('{} files in folder, all png images.'.format(len(contents)))
        return True


def print_dictionary(pt='./anonymizer_dictionary.pkl'):
    """
    Function that prints reads an anonymizer dictionary and prints it.

    Example:
    >>> import thicom
    >>> thicom.print_dictionary('/path/to/anonymizer_dictionary.pkl')

     -----------------------------------------------------------------------
    | No. |                   Patient's Name                   |   Alias    |
    | --- | -------------------------------------------------- | ---------- |
    | 0.  | Patient1                                           | Subject1   |
    | 1.  | Patient2                                           | Subject2   |
    | 2.  | Patient3                                           | Subject3   |
    | 3.  | Patient4                                           | Subject4   |
    | 4.  | Patient5                                           | Subject5   |
    | 5.  | Patient6                                           | Subject6   |
                            ............

    :param pt: A path of a pickle file storing a dictionary (str).
    """
    from thicom.anonymizer import Anonymizer
    result = Anonymizer.read_diction(diction_path=pt)
    print(result)


__version__ = '0.3.1'
__version_info__ = (0, 3, 1)
