from __future__ import print_function
import numpy as np
import shutil
import re
# Proprietary imports
from thicom.components import *
from thicom.converter import Converter

if sys.version[0] == '2': input = raw_input


class Preprocessor:

    def __init__(self, parent_dirs='.', verbose=False, diction=None, log_dir='./logs', pre_check=True, run=False,
                 yes_to_all=False):
        """
        This class handles any pre-processing operation concerning MRIs. First a compatibility check is performed which
        searches for:
        1. Patients with DaT scans in DICOM format (with a DICOMDIR).
        2. Patients without MRI DICOMDIRs.
        3. Multiple MRI DICOMDIRS for a single patient.
        4. Wrong directory structure (e.g NPD/Patient/MRI/DICOMDIR instead of NPD/Patient/DICOMDIR)
        5. Wrong directory name (D.Patient, D1 Patient, D1a Patient, etc)
        Running this will: Attempt to correct as many of the previous errors as possible, create and apply an
        anonymization scheme, convert all DICOM images to png (while generating all necessary log files), structure the
        directories according to the scheme while removing any obsolete file. Then it searches for all MRIs containing
        'T1' in their name and stores them in a separate directory.
        :param parent_dirs: path indicating where to start from (str).
        :param verbose: True/False whether or not user wants his screen flooded with messages (bool).
        :param diction: OrderedDict containing the anonymization scheme, or a path to a pickle-stored OrderedDict.
        :param log_dir: where to store log files (str).
        :param run: True/False whether or not to run on instantiation (bool).
        :param yes_to_all: True will bypass all user confirmations (bool).
        """

        if isinstance(parent_dirs, str): parent_dirs = [parent_dirs]
        self.parent_dirs = parent_dirs
        self.verbose = verbose
        self.diction = diction
        self.log_dir = log_dir
        self.yes_to_all = yes_to_all

        if pre_check:
            flag = self.pre_check()
        else:
            flag = True

        if run:
            if not flag:
                # No yes_to_all available here, user must answer if he wants to proceed!
                check = input('Do you want to ignore the structure errors and proceed? (Y/N) ')
                if check.lower() in ('yy', 'yes to all', 'yes_to_all'): self.yes_to_all = True
                if check.lower() in ('n', 'no'): return
            self.handle_all(parent_dirs=parent_dirs)
            self.gather_t1(parent_dirs=parent_dirs)

    def handle_all(self, parent_dirs='.', diction=None):
        """
        This method handles converting DICOM MRIs to png images, anonymizing and neatly structuring their respective
        directories.
        :param parent_dirs: A path from which to start searching for patients to anonymize/convert. (str)
        :param diction: An anonymizer_dictionary from a former procedure. (OrderedDict/Path to a pickle object storing
                                                                           an OrderedDict)
        """
        if not diction: diction = self.diction

        if isinstance(parent_dirs, str): parent_dirs = [parent_dirs]
        parent_dirs = [os.path.abspath(x) for x in parent_dirs]

        previous = 0
        anonymized = 0
        converted = 0
        failed = 0
        for i, parent_dir in enumerate(parent_dirs):

            if not os.path.isdir(parent_dir):
                raise OSError('Invalid path: {}'.format(parent_dir))
            if self.verbose: print('Attempting to handle all patients under directory {}'.format(parent_dir))
            # handle MRI images
            res = self.mri_handler(parent_dir=parent_dir, diction=diction)
            # structure directories and remove DICOMDIR files
            self.structure_directories(parent_dir=parent_dir)

            previous = res[0]
            anonymized += res[1] - previous
            converted += res[2]
            failed += res[3]

            if self.verbose:
                if i == 0: print('Dictionary\'s previous entries: {}'.format(res[0]))
                print('Successfully anonymized {} images.'.format(res[1]-previous))
                print('Successfully converted {} DICOM images to png.'.format(res[2]))
                if res[3]: print('Failed to convert {} DICOM images.'.format(res[3]))

        print('\n------------------ REPORT -------------------')
        if previous: print('{:<40} {}'.format('Previous entries:', previous))
        print('{:<40} {}'.format('Patients anonymized:', anonymized))
        if previous: print('{:<40} {}'.format('Dictionary\'s total entries:', previous + anonymized))
        print('{:<40} {}'.format('DICOM images converted to png:', converted))
        if failed: print('{:<40} {}'.format('DICOM images failed to convert:', failed))
        print()

    def structure_directories(self, parent_dir='.'):
        """
        This method is supposed to be called after mri_handler. It searches for DICOM directories and
        deletes them. Then finds all .png images generated by the handler and moves them to an MRI
        directory. Also removes all DICOMDIR files.
        :param parent_dir: Path from where to search for DICOMDIR files (str)
        """

        # search for patient directories based on DICOMDIR files
        patient_dirs = find_dcmdir(pts=parent_dir)
        if not patient_dirs:
            print('No DICOMDIR files found, cannot perform this operation.')
            return

        if not self.yes_to_all:
            # query user and generate a list of patients
            print('Preparing to structure directories.')
            for i, d in enumerate(patient_dirs):
                print('{:<5}{}'.format(str(i) + '.', d))
            key = input('Which DICOMDIR(s) do you want to convert?\n(1, 2, 3, ... / multiple '
                        'indice separated by a single space / 0 for none / anything else for all)\n')
            if key.isdigit():
                if int(key) == 0:
                    print('Exiting')
                    sys.exit()
                patient_dirs = [patient_dirs[int(key) - 1]]
            elif all([x.isdigit() for x in key.split()]) and key != '':
                patient_dirs = [patient_dirs[int(i) - 1] for i in key.split()]

        for directory in patient_dirs:

            # what to delete
            directory_items = [os.path.join(directory, x) for x in os.listdir(directory) if x[-4:] != '.png' and
                               '0.dat' not in ''.join(x.lower().split())]

            # remove everything in the directory
            if self.verbose: print('Removing all irrelevant files and directories in {}'.format(directory))
            for d in directory_items:
                try:
                    # remove directories
                    shutil.rmtree(d)
                except OSError:
                    # remove files
                    os.remove(d)

            # make MRI directory and move all images in there
            if self.verbose: print('Creating an MRI directory')
            mri_dir = os.path.join(directory, '1.MRI')
            os.mkdir(mri_dir)
            imgs = [os.path.join(directory, x) for x in os.listdir(directory) if x[-4:] == '.png']
            for img in imgs:
                shutil.move(img, mri_dir)
            if self.verbose: print('Moved {} images in {}/1.MRI'.format(len(imgs), directory))

    def mri_handler(self, parent_dir='.', diction=None):
        """
        This method handles all MRI images in the dataset. First it creates/updates the anonymizer_dictionary
        which contains the patient-alias mappings. Then it translates the patient's directories to their respective
        mappings. After that it performs the conversion from DICOM image to png for each patient. Finally it anonymizes
        the conversion_log generated from the previous step.
        :param parent_dir: A path from which to start searching for patients to anonymize/convert. (str)
        :param diction: An anonymizer_dictionary from a former procedure. (OrderedDict/Path to a pickle object storing
                                                                           an OrderedDict)
        :return A tuple containing the anonymization and conversion results (4 elements in total):
                (number of previous dictionary entries, number of current dictionary entries, number of images
                successfully converted to png, number of images that failed the conversion). (tuple)
        """

        if not diction: diction = self.diction
        if not os.path.isdir(parent_dir):
            raise OSError('Invalid path: {}'.format(parent_dir))

        if self.verbose: print('Proceeding to create and apply an anonymization scheme...')
        # directory anonymization
        from thicom.anonymizer import Anonymizer
        patient_dirs = [os.path.join(os.path.abspath(parent_dir), x) for x in os.listdir(parent_dir)
                        if os.path.isdir(os.path.join(os.path.abspath(parent_dir), x))]
        anon = Anonymizer(paths=patient_dirs, diction=diction, verbose=self.verbose, log_dir=self.log_dir, run=True,
                          only_dirs=True, yes_to_all=self.yes_to_all)
        self.yes_to_all = anon.yes_to_all  # In case yes_to_all was updated...
        self.diction = anon.dct
        anon_results = (anon.get_results())

        if self.verbose: print('Attempting to convert all DICOM images to png...')
        # conversion to png and anonymize the conversion_log.txt
        conv = Converter(dicom_root_path=parent_dir, run=True, log_dir=self.log_dir, verbose=self.verbose, cleanup=True,
                         yes_to_all=self.yes_to_all)
        self.yes_to_all = conv.yes_to_all  # In case yes_to_all was updated...
        conv_results = (conv.get_results())
        anon.anonymize_log(conv_log=os.path.join(self.log_dir, 'conversion_log.txt'),
                           patient_log=os.path.join(self.log_dir, 'patient log.txt'))
        return anon_results + conv_results

    def gather_t1(self, parent_dirs=None, destination='./selection'):
        """
        This method searches for and copies all T1 MRI sequences under a patient_dir to a specified destination, while
        preserving the existing patient structure.
        :param parent_dirs: A directory or list of directories under which we can find the existing patient structure
                           (string/list of strings).
        :param destination: The directory where we will copy the images (string).
        """

        if not parent_dirs: parent_dirs = self.parent_dirs
        if isinstance(parent_dirs, str): parent_dirs = [parent_dirs]
        parent_dirs = [os.path.abspath(x) for x in parent_dirs]

        destination = os.path.abspath(destination)

        for parent_dir in parent_dirs:

            # check if parameters are valid
            if not os.path.isdir(parent_dir):
                raise OSError('Invalid path: {}'.format(parent_dir))
            parent_dir = os.path.abspath(parent_dir)
            if not os.path.isdir(destination):
                if os.path.exists(destination):
                    raise OSError('Destination directory is a file: {}'.format(destination))
                os.mkdir(destination)

            # get a list of directories (PD/NPD)
            dir_lst = [os.path.join(parent_dir, d) for d in os.listdir(parent_dir)
                       if os.path.isdir(os.path.join(parent_dir, d))]
            c = 0

            for d in dir_lst:

                # create a target (PD/NPD) directory and an 'mri' dir under that
                new_dir = os.path.join(destination, os.path.basename(d))
                try:
                    os.mkdir(new_dir)
                except OSError:
                    pass  # directory already exists
                mri_dir = os.path.join(new_dir, 'MRI')
                try:
                    os.mkdir(mri_dir)
                except OSError:
                    pass  # directory already exists

                # get a list of patients
                patient_list = [os.path.join(d, p) for p in os.listdir(d) if os.path.isdir(os.path.join(d, p))]

                for p in patient_list:
                    try:
                        # search for all png images under the patient
                        png_list = find_png(os.path.join(p, '1.MRI'), contains='t1', verbose=self.verbose)

                        if png_list:
                            # create a patient directory under the mri directory
                            sel_pat_dir = os.path.join(mri_dir, os.path.basename(p)[7:])
                            os.mkdir(sel_pat_dir)

                            c += len(png_list)

                            # copy all images to the newly created patient directory
                            if self.verbose: print('Copying images to {}'.format(sel_pat_dir))
                            for img in png_list:
                                shutil.copy(img, sel_pat_dir)

                    except OSError:
                        print('No T1-sequence images for {}'.format(os.path.basename(p)))

            total_png = len(find_png(destination))

            if c == 0:
                print('{} images found but no images were copied'.format(total_png))
                return
            if c != total_png:
                print('{} images found but only {} images copied'.format(total_png, c))

    def pre_check(self, parent_dirs=None, action=False):
        """
        Preliminary check for one DICOMDIR-per-patient condition. Also checks if directory name and structure are
        appropriate. Patient directories should be named "D[0-9]. Lastname Firstname" and the DICOMDIR file should
        be located directly under the patient's directory. If action is selected, it will attempt to fix most of the
        errors that appear.

        Specifically it checks for:
        1. Patients with DaT scans in DICOM format (with a DICOMDIR).
        2. Patients without MRI DICOMDIRs.
        3. Multiple MRI DICOMDIRS for a single patient.
        4. Wrong directory structure (e.g NPD/Patient/MRI/DICOMDIR instead of NPD/Patient/DICOMDIR)
        5. Wrong directory name (D.Patient, D1 Patient, D1a Patient, etc)

        :param parent_dirs: Path to directory or list of directories each containing NPD/PD subdirectories
                            (str/list of str)
        :param action: True if user wants to take action (e.g deleting excessive DICOMDIRs) (bool).
        :return: True if we have one DICOMDIR per patient, False otherwise (bool).
        """
        if not parent_dirs: parent_dirs = self.parent_dirs
        if isinstance(parent_dirs, str): parent_dirs = [parent_dirs]
        parent_dirs = [os.path.abspath(x) for x in parent_dirs]
        normal = []
        issues = {'none': [], 'many': [], 'dcm-without-dir': [], 'dir-without-dcm': []}
        if not action: issues['dat'] = []

        print('Performing a preliminary check.')

        # Traverses parent directories
        for parent_dir in parent_dirs:
            class_dirs = [os.path.join(parent_dir, x) for x in os.listdir(parent_dir)
                          if os.path.isdir(os.path.join(parent_dir, x))]

            # Traverses class directories (PD, NPD)
            for class_dir in class_dirs:

                patient_dirs = [os.path.join(class_dir, x) for x in os.listdir(class_dir)
                                if os.path.isdir(os.path.join(class_dir, x))]

                # Traverses patient directories (Subject1, Subject2, etc.)
                print('Checking {}'.format(os.path.join(parent_dir, class_dir)))
                for patient_dir in tqdm(patient_dirs, ):

                    dats = 0  # dat scan DICOMDIR counter for current patient

                    # Searches for all DICOMDIRs in current patient's directory, while suppressing the output
                    with suppress_stdout():
                        dicomdirs = find_dcmdir(patient_dir)

                    # If there is no DICOMDIR there is a problem
                    if not dicomdirs:
                        if self.verbose: print('No DICOMDIR file in: {}'.format(patient_dir))
                        issues['none'].append(patient_dir)
                        continue

                    # If there is one or more, first report/remove all dat scans
                    for dicomdir in dicomdirs:
                        if 'dat' in os.path.basename(dicomdir).lower():
                            if action:
                                curr = os.getcwd()
                                self.dicom_dat(dicomdir)
                                self.structure_dat_directory(dicomdir)
                                os.chdir(curr)
                            else:
                                dats += 1
                                issues['dat'].append(dicomdir)

                    # Then check again for DICOMDIRs, again suppressing the output.
                    # If no action is taken no need to check again.
                    if action:
                        with suppress_stdout():
                            dicomdirs = find_dcmdir(patient_dir)

                    # Check if a patient that has a DICOMDIR doesn't have any DICOM images
                    for d in dicomdirs:
                        has_dicom = False
                        for directory, _, file_lst in os.walk(d):
                            if has_dicom:
                                break
                            for f in file_lst:
                                if has_dicom:
                                    break
                                if is_dicom(os.path.join(directory, f)):
                                    has_dicom = True
                        if not has_dicom:
                            if self.verbose: print('Patient {} has no DICOM images while having '
                                                   'a DICOMDIR'.format(os.path.basename(d)))
                            if action:
                                os.remove(d)
                            else:
                                issues['dir-without-dcm'].append(d)

                    # This would mean that we only have DaT scan DICOMDIRs for the current patient
                    if len(dicomdirs)-dats == 0:
                        if self.verbose: print('No MRI DICOMDIR file in: {}'.format(patient_dir))
                        issues['none'].append(patient_dir)
                        continue

                    # If there are multiple DICOMDIRs there is a problem
                    if len(dicomdirs)-dats > 1:
                        if self.verbose: print('Multiple DICOMDIRs detected in: {}'.format(patient_dir))
                        issues['many'].append(patient_dir)
                        continue

                    if len(dicomdirs)-dats == 1:
                        # Reaching here would mean that everything is normal with this patient
                        # i.e. we only have one DICOMDIR for this patients (excluding the dat scans)
                        # the DICOMDIR corresponding to the MRI should be the one with the shortest path
                        sh = np.argmin(map(len, dicomdirs))
                        normal.append(dicomdirs[sh])
                        # if action=False this could return a wrong result if the directories don't have a correct
                        # structure.

        # Check if the patients that don't have a DICOMDIR have DICOM images
        if self.verbose: print('Checking if patients with DICOM images don\'t have a DICOMDIR file.')
        for pat in issues['none']:
            # Search for DICOM images for each patient that doesn't have a DICOMDIR
            with suppress_stdout():
                dcm = find_dcm(pts=pat)
            if self.verbose: print('patient: {}, dicom images: {}'.format(pat, len(dcm)))
            # If there is a DICOM image that doesn't contain the string 'dat' in it's parent directory,
            # append the patient to the dictionary with the relevant issue
            if any(['dat' not in os.path.basename(os.path.basename(d.lower())) for d in dcm]):
                if action:
                    conv = Converter(dicom_root_path=pat, run=True, verbose=self.verbose, yes_to_all=self.yes_to_all,
                                     cleanup=True)
                    self.yes_to_all = conv.yes_to_all  # in case yes_to_all changed
                    normal.append(pat)
                else:
                    issues['dcm-without-dir'].append(pat)
        print()
        if issues['dcm-without-dir']:
            # Filter out the previous category so that it doesnt't contain patients from this one
            issues['none'] = filter(lambda p: p not in issues['dcm-without-dir'], issues['none'])

            # Display issues to the user
            print('No DICOMDIR files were found for the following patients that have DICOM images:')
            for i, d in enumerate(issues['dcm-without-dir']):
                print('{:<3} {}'.format(str(i+1)+'.', os.path.relpath(d)))
            print()

        if issues['dir-without-dcm']:
            print('No DICOM images were found for the following patients that have a DICOMDIR:')
            for i, d in enumerate(issues['dir-without-dcm']):
                print('{:<3} {}'.format(str(i+1)+'.', os.path.relpath(d)))
            print()

        # Display issues to user
        if issues['none']:
            print('No DICOM files were found for the following patients:')
            for i, d in enumerate(issues['none']):
                print('{:<3} {}'.format(str(i+1)+'.', os.path.relpath(d)))
            print()
            # TODO: dummy DICOMDIR for patients with no DICOMDIR

        if issues['many']:
            print('Multiple DICOMDIR files were found for the following patients:')
            for i, d in enumerate(issues['many']):
                print('{:<3} {}'.format(str(i+1)+'.', os.path.relpath(d)))
            print()

        if not action:
            if issues['dat']:
                print('DICOMDIR files were found for the following patient\'s dat scans:')
                for i, d in enumerate(issues['dat']):
                    print('{:<3} {}'.format(str(i+1)+'.', os.path.relpath(d)))
                print()

        # Check for depth consistency of DICOMDIR files. Directory structure in this phase should be:
        # parent_dir/class_dir/patient_dir/DICOMDIR (DICOMDIR's directory should have a depth of 2)
        # a wrong depth is an indication of a wrong directory structure
        wrong_depth = check_depth(normal, normal_depth=round(average_depth(normal)), relative=True)
        if wrong_depth:
            if not action:
                print('Wrong directory structure in the following patients:')
                for i, d in enumerate(wrong_depth):
                    print('{:<3} {}'.format(str(i+1)+'.', os.path.relpath(d)))
                print()

                # Filter normal patients so that they don't contain any patients with a wrong depth. This also cancels
                # out the randomness that occurs when action=False with a dat DICOMDIR and a wrong directory structure
                normal = filter(lambda p: p not in wrong_depth, normal)
            else:
                print()
                for d in wrong_depth:
                    if self.verbose: print('Moving DICOMDIR from {} to {}'.format('/'.join(d.split('/')[-4:]),
                                                                                  '/'.join(d.split('/')[-4:-1])))
                    shutil.move(os.path.join(d, 'DICOMDIR'), os.path.dirname(d))
                    normal[normal.index(d)] = os.path.dirname(d)
                print()

        # Check for naming consistency
        if not action:
            # Log the directories that don't have a consistent naming scheme
            wrong_dirname = []
            for name in normal:
                basename = os.path.basename(name)
                # check if they comply to the naming convention (e.g "D1. Lastname Firstname")
                result = re.match('^D[0-9]\. ', basename)
                # log the ones that don't
                if not result:
                    wrong_dirname.append(name)
            # display them
            if wrong_dirname:
                if self.verbose:
                    print('Possibly wrong directory name in the following patients:')
                    for i, d in enumerate(wrong_dirname):
                        print('{:<3} {}'.format(str(i+1)+'.', os.path.relpath(d)))
                    print()
            # filter the normal ones so that they don't include those that don't comply with the convention
            normal = filter(lambda p: p not in wrong_dirname, normal)
        else:
            # In this case we disregard the convention altogether and remove the "D[0-9]. " expression from the string
            for i, name in enumerate(normal):
                dirname = os.path.dirname(name)
                basename = os.path.basename(name)
                new_name = re.sub('^D[0-9]?[a-z]?\.? ?', '', basename)
                if self.verbose: print('Renaming  {:<30} to  {}'.format(basename[:30], new_name))
                normal[i] = os.path.join(dirname, new_name)
                os.rename(name, normal[i])
            print()

        # Display normal patients to user:
        if self.verbose:
            if normal:
                print('Normal patients:')
                for i, d in enumerate(normal):
                    print('{:<3} {}'.format(str(i+1)+'.', os.path.relpath(d)))
                print()

        # Check for dicomdirs one final time
        if action:
            with suppress_stdout:
                dicomdirs = find_dcmdir()

            # Return True if no issues were found, or the issues were dealt with
            if len(normal) == len(dicomdirs):
                return True
            else:

                return False
        else:
            return False if any(issues.values()) else True

    def dicom_dat(self, pt):
        """
        Converts dat scans from DICOM to png.
        :param pt: Path for the dat scan directory (str).
        """
        if self.verbose: print('Converting DaT scan DICOM images to png from {}'.format(pt))
        try:
            conv = Converter(dicom_root_path=pt, run=True, log_dir='/tmp', verbose=self.verbose, cleanup=True,
                             same_name=True, yes_to_all=self.yes_to_all)
            self.yes_to_all = conv.yes_to_all  # in case yes_to_all was changed
            conv_results = conv.get_results()
            print('{:<40} {}'.format('DICOM images converted to png:', conv_results[0]))
            if conv_results[1]: print('{:<40} {}'.format('DICOM images failed to convert:', conv_results[1]))
        except ValueError:
            print('No DICOM files in {}'.format(pt))

    def structure_dat_directory(self, pt):
        """
        Removes everything from a dat scan directory (besides all png images).
        :param pt: Path for the dat scan directory (str)
        """
        if not self.yes_to_all:
            # query user and generate a list of patients
            print('Preparing to structure directory', pt)
            key = input('Do you wand to proceed? (will remove all files besides .png images)  ')
            if key.lower() in ('yy', 'yes to all', 'yes_to_all'):
                self.yes_to_all = True
            if key.lower() in ('n', 'no'): return False

        # what to delete
        items = [os.path.join(pt, x) for x in os.listdir(pt) if x[-4:] != '.png']

        # remove everything in the directory
        if self.verbose: print('Removing all irrelevant files and directories in {}'.format(pt))
        for i in items:
            try:
                # remove directories
                shutil.rmtree(i)
            except OSError:
                # remove files
                os.remove(i)
