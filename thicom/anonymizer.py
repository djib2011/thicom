#!/usr/bin/python
from __future__ import print_function
from difflib import SequenceMatcher
from collections import OrderedDict
import dicom
import sys
import os
import io
try:
    import cPickle as pkl
except ImportError:
    import pickle as pkl
# Proprietary imports:
from thicom.components import find_dcm, find_dcmdir, is_dicom

if sys.version[0] == '2': input = raw_input


class Anonymizer:

    def __init__(self, paths=None, diction=None, verbose=False, only_dirs=True, similarity_check=True, run=False,
                 log=True, log_dir='./logs', yes_to_all=False):
        """
        This class creates and updates a mapping of patient names with aliases and anonymizes dicom images.
        :param verbose: True/False whether or not to output information to screen (bool).
        :param only_dirs: True if user doesn't want to anonymize images but only directories (bool).
        :param similarity_check: True/False whether or not to perform string similarity check (bool).
        :param run: True/False whether or not to anonymize files on instantiation(bool).
        :param log: True/False whether or not to keep a log (bool).
        :param log_dir: Path for the directory where the logs are to be stored (string).
        :param paths: A list of paths (string).
        :param diction: Dictionary of names:aliases. An OrderedDict or a path to a pickle object containing
                        an OrderedDict.
        :param yes_to_all: Bypass all user confirmation (bool).
        """
        if not paths: paths = '.'
        self.paths = [os.path.abspath(x) for x in paths] if isinstance(paths, list) else os.path.abspath(paths)
        self.verbose = verbose
        self.similar = similarity_check
        self.only_dirs = only_dirs
        self.log = log
        self.dct = None
        self.failed = []
        self.attempted = 0
        self.processed = 0
        self.previous_entries = 0
        self.yes_to_all = yes_to_all
        self.threshold = 0.7  # string compare threshold
        if log_dir: self.log_dir = os.path.abspath(log_dir)
        if self.log: self.log_dict = {}
        created = False

        # store current location
        curr = os.getcwd()

        # read dictionary
        if diction:
            if isinstance(diction, OrderedDict):
                self.dct = diction
            else:
                if not os.path.exists(diction):
                    raise OSError('Invalid path: {}'.format(diction))
                try:
                    self.dct = pkl.load(open(diction, 'rb'))
                except:
                    raise TypeError('Incompatible type for dictionary.')

        # if no dictionary was specified
        else:
            # try to find a dictionary if none is defined
            if os.path.exists('anonymizer_dictionary.pkl'):
                check = input('Found dictionary from previous procedure: ./anonymizer_dictionary.pkl. '
                              'Do you want to use this one? (Y/N) ')
                if check.lower() in ('', 'y', 'yes', 'ok', 'yy', 'yes_to_all', 'yes to all'):
                    self.dct = pkl.load(open('anonymizer_dictionary.pkl', 'rb'))
                if check.lower() in ('yy', 'yes_to_all', 'yes to all'):
                    self.yes_to_all = True

            if os.path.exists('logs/anonymizer_dictionary.pkl'):
                check = input('Found dictionary from previous procedure: ./logs/anonymizer_dictionary.pkl. '
                              'Do you want to use this one? (Y/N) ')
                if check.lower() in ('', 'y', 'yes', 'ok', 'yy', 'yes_to_all', 'yes to all'):
                    self.dct = pkl.load(open('logs/anonymizer_dictionary.pkl', 'rb'))
                if check.lower() in ('yy', 'yes_to_all', 'yes to all'):
                    self.yes_to_all = True

            # if no dictionary was specified or found try to create one
            if not self.dct:
                created = self.create_anon_dict(self.paths)
                if not created:
                    sys.exit()

        # if dictionary was loaded, try to update it
        if not created:
            if not isinstance(self.dct, OrderedDict):
                raise TypeError('File should be an OrderedDict')
            # store how many entries the dictionary had previously
            self.previous_entries = len(self.dct)
            # update dict with paths
            self.update_dict(self.paths)

        if run:
            if self.yes_to_all:
                run = True
            else:
                check = input("Proceeding will replace all DICOM images' \"Patient's Names\" to aliases:\n"
                              "e.g \"John Doe\" --> \"Subject1\".\nDo you want to proceed? (Y/N)  ")
                run = False if check.lower() not in ('', 'true', 't', 'y', 'yes', 'proceed') else True
                if check.lower().replace(' ', '') in ('yy', 'yes_to_all', 'yestoall'):
                    self.yes_to_all = run = True

        if run:
            # begin anonymization procedure
            proceed = self.anonymize()

            # if single dicom anonymization no logs are generated
            if proceed:
                # log
                if not self.log_dir:
                    file_dir = self.paths[0] if isinstance(self.paths, list) else self.paths
                else:
                    file_dir = self.log_dir
                if not os.path.isdir(self.log_dir):
                    os.mkdir(self.log_dir)
                os.chdir(file_dir)
                # report
                print('Total number of dicom images: {}'.format(self.attempted))
                print('Number of images successfully processed: {}'.format(self.processed))
                print('Number of images failed: {}'.format(len(self.failed)))

                # create the patient log even if we don't anonymize the images themselves
                if self.only_dirs:
                    self.log_dict = self.create_patient_log()

                # write to file
                with open('patient aliases.txt', 'wb') as f:
                    print('Writing name-alias mappings to {}/patient aliases.txt'.format(file_dir))
                    f.write('{:<40}{}\n'.format('Patient Name', 'Patient Alias'))
                    for key, val in self.dct.items():
                        f.write('{:<40}{}\n'.format(key, val))
                if self.failed:
                    with open('failed dicom.txt', 'wb') as f:
                        print('Writing failed dicom paths to {}/failed dicom.txt'.format(file_dir))
                        for x in self.failed:
                            f.write('{}\n'.format(x))
                if self.log:
                    with open('patient log.txt', 'wb') as f:
                        print('Writing mapping log to {}/patient log.txt'.format(file_dir))
                        f.write('{:<40}{}\n'.format('Patient Name', 'Patient Alias'))
                        for key, val in self.log_dict.items():
                            f.write('{:<40}{}\n'.format(key, val))

                # save as a pickle object
                pkl.dump(self.dct, open('anonymizer_dictionary.pkl', 'wb'))

        os.chdir(curr)

    def anonymize_dicom(self, dcm, alias, original=None):
        """
        This method 'anonymizes' a dicom image by replacing it's "Patient's Name" with an alias (e.g Subject1).
        :param dcm: path of a dicom image (string).
        :param alias: name with which to replace the "patient's Name" (string).
        :param original: original name for string comparison (string)
        """
        self.attempted += 1
        ds = dicom.read_file(dcm)
        if self.similar:
            if original:
                comp = SequenceMatcher(None, ds.PatientsName.lower(), original.lower()).ratio()
                if comp > self.threshold:
                    raise TypeError('String compare failed, distance between {} and {}:{} < {} threshold)'
                                    '.'.format(ds.PatientsName.lower(), original.lower(), comp, self.threshold))
            else:
                raise NotImplementedError("Need patient's name to compare strings.")
        old = ds.PatientsName
        ds.PatientsName = alias
        try:
            ds.save_as(dcm + '_anon')
            if self.verbose:
                print("Replaced patient's name from {} to {} for dicom file: {}".format(old, alias, dcm.split('/')[-1]))
                if self.log:
                    if old not in self.log_dict.keys():
                        self.log_dict[old] = alias
                    else:
                        if self.log_dict[old] == alias:
                            raise KeyError('Two aliases for the same patient:\nPatient: {}\n Old Alias: {}\n'
                                           'New Alias: {}'.format(old, self.log_dict[old], alias))
                self.processed += 1
        except ValueError:
            print('ValueError when trying to save dicom image {}'.format(dcm))
            self.failed.append(dcm)

    def anonymize_patient(self, patient_name):
        """
        This method 'anonymizes' all images under that belong to a specific patient.
        :param patient_name: A directory containing the images we want to anonymize (string).
                             The directory's name should be the name of the patient.
        """
        if '/' in patient_name:
            patient_name = patient_name.split('/')[-1]
        patient_alias = self.dct[patient_name]
        ls = find_dcm(patient_name)
        if not self.similar:
            patient_name = None
        for d in ls:
            self.anonymize_dicom(d, patient_alias, patient_name)

    def create_anon_dict(self, pts):
        """
        This method creates an OrderedDict that maps patient's names to their aliases.
        The input should be the directory in which there are folders of each patient with their names on them.
        Example:  {'Subject1' : 'John Doe', 'Subject2' : 'Jane Doe'}
        :param pts: A path or list of paths. (string/list of strings)
        """
        src_dir = os.getcwd()
        if isinstance(pts, list):
            p = pts[0]
            if not os.path.exists(p):
                raise OSError('Invalid path: {}'.format(p))
            os.chdir(p)
            patients = [x for x in os.listdir('.') if os.path.isdir(x)]
            ids = ['Subject' + str(x) for x in range(1, len(patients) + 1)]
            self.dct = OrderedDict(zip(patients, ids))
            os.chdir(src_dir)
            for i in range(1, len(pts)):
                stdout_snap = sys.stdout
                sys.stdout = io.BytesIO()
                self.update_dict(pts[i], no_check=True)
                sys.stdout = stdout_snap
        elif isinstance(pts, str):
            if os.path.exists(pts):
                if os.path.isdir(pts):
                    os.chdir(pts)
                elif 'dicomdir'in pts:
                    pts = os.path.split(pts)[0]
                    os.chdir(pts)
                else:
                    return False
            else:
                raise OSError('Invalid path: {}'.format(pts))
            patients = [x for x in os.listdir(pts) if os.path.isdir(x)]
            ids = ['Subject' + str(x) for x in range(1, len(patients) + 1)]
            self.dct = OrderedDict(zip(patients, ids))
        else:
            raise TypeError('Enter either a path string or a list of path strings.')
        print('Dictionary with {} mappings created.'.format(len(self.dct)))
        if self.verbose: print(self.dct)
        os.chdir(src_dir)
        return True

    def update_dict(self, pts, no_check=False):
        """
        This method updates the OrderedDict with new entries, generated from the directory names under path 'pt'.
        :param pts: A path which contains directories with the names of patients. (str)
        :param no_check: Option to skip user confirmation. (bool)
        """
        print('Updating anonymzer dictionary...')
        if self.yes_to_all: no_check = True
        if isinstance(pts, str):
            pts = [pts]
        patients = []
        for pt in pts:
            if not os.path.exists(pt):
                raise OSError('Invalid path: {}'.format(pt))
            os.chdir(pt)
            patients += [x for x in os.listdir(pt) if os.path.isdir(x) and x not in self.dct.keys()]

        # select which patients to add to the dictionary
        if patients and not no_check:
            similar = {}
            for p in patients:
                for a in self.dct.keys():
                    comp = SequenceMatcher(None, p, a).ratio()
                    if comp > self.threshold:
                        similar[p] = (a, comp)
            for pat in similar.keys():
                print('{:<30} is similar to previous entry {:<30} with a score of '
                      '{:.2f}.'.format(pat[:30], similar[pat][0][:30], similar[pat][1]))
            for i, p in enumerate(patients):
                print('{:>3}. {}'.format(i+1, p))
            key = input('Which patients do you want to add to the dictionary?\n(1, 2, 3, ... / multiple '
                        'indice separated by a single space / 0 for none / anything else for all)\n')
            if key.isdigit():
                if int(key) == 0:
                    return
                patients = [patients[int(key) - 1]]
            elif all([x.isdigit() for x in key.split()]) and key != '':
                patients = [patients[int(i) - 1] for i in key.split()]

        last = len(self.dct.items())
        ids = ['Subject' + str(x) for x in range(last + 1, last + len(patients) + 1)]
        prev = len(self.dct)
        self.dct.update(zip(patients, ids))
        print('{} new mappings added.'.format(len(self.dct) - prev)) if (len(self.dct) - prev) != 1 \
            else print('1 new mapping added.')
        if self.verbose: print(zip(patients, ids))

    def anonymize(self, pts=None):
        """
        This method traverses directories finding dicom images and replacing their "Patient's Name" with
        aliases according to the mapping from the OrderedDict.
        :param pts: A path or list of paths (string/list of strings).
        """
        single_dicom = False
        if not pts: pts = self.paths

        if isinstance(pts, list):
            pts = [os.path.abspath(x) for x in pts]
            for p in pts:
                if not os.path.exists(p):
                    raise OSError('Invalid path: {}'.format(p))
                os.chdir(p)
                dirs = os.listdir('.')
                for d in dirs:
                    if d in self.dct:
                        if not self.only_dirs:
                            self.anonymize_patient(d)
                        if self.verbose: print('Renaming {} to {}'.format(d, self.dct[d]))
                        os.rename(d, self.dct[d])
        elif isinstance(pts, str):
            if not os.path.exists(pts):
                raise OSError('Invalid path: {}'.format(pts))
            if is_dicom(pts):
                self.anonymize_dicom(dcm=pts, alias='anonymous')
                single_dicom = True
            elif 'dicomdir' in pts:
                pts = os.path.split(pts)[0]
            if os.path.isdir(pts):
                os.chdir(pts)
                dirs = os.listdir('.')
                for d in dirs:
                    if d in self.dct:
                        if not self.only_dirs:
                            self.anonymize_patient(d)
                        os.rename(d, self.dct[d])
        else:
            raise TypeError('Enter either a path string or a list of path strings.')
        print('Patients successfully anonymized.')

        # remove all non-anonymous images
        if not self.only_dirs:
            self.cleanup(pts=pts)

        # return value specifies if the script will continue with logging after anonymization
        return False if single_dicom else True

    def cleanup(self, pts=None):
        """
        This method searches for all dicom images under a specified directory and deletes the
        ones that do not end in _anon.
        :param pts: A path or list of paths(string/list of strings).
        """
        if self.verbose: print('Cleaning up...')
        if not pts:
            pts = self.paths
        cnt = 0
        if isinstance(pts, list):
            pts = [os.path.abspath(x) for x in pts]
            for p in pts:
                c = 0
                if not os.path.exists(pts):
                    raise OSError('Invalid path: {}'.format(p))
                dcm_list = find_dcm(p)
                old_dcm = [x for x in dcm_list if x[-5:] != '_anon']
                for d in old_dcm:
                    os.remove(d)
                    c += 1
                cnt += c
                if self.verbose:
                    print('{} images deleted from directory {}.'.format(c, p))
            if self.verbose:
                print('A total of {} images were deleted under directory/ies {}.'.format(cnt, pts))
        elif isinstance(pts, str):
            dcm_list = find_dcm(pts)
            old_dcm = [x for x in dcm_list if x[-5:] != '_anon']
            for d in old_dcm:
                os.remove(d)
                cnt += 1
            if self.verbose:
                print('A total of {} images were deleted under directory {}.'.format(cnt, os.path.abspath(pts)))
        else:
            raise TypeError('Enter either a path string or a list of path strings.')

    def create_patient_log(self, pts=None):
        """
        Creates a patient log from DICOMDIRs in already anonymized directories
        :param pts: Path or a list of paths (str/list of str)
        :return: A dictionary containing mapping patient names to their aliases (dict)
        """
        print('Creating patient log:')
        if not pts: pts = self.paths
        dcmdir_list = find_dcmdir(pts=pts)
        log = {}
        for d in dcmdir_list:
            ds = dicom.read_dicomdir(os.path.join(d, 'DICOMDIR'))
            # find and isolate the patient's alias in the path string
            alias = d[d.find('Subject'):].split('/')[0]
            # unfortunately DICOMDIRs don't have a field named PatientsName, so we have to search through the
            # string to find the line where it is and isolate it from the rest of the string. Thankfully
            # it is in the end of the line so we can just throw away the first 57 characters to keep it
            patients_name = None
            for line in str(ds).split('\n'):
                if 'patient\'s name' in line.lower():
                    patients_name = line[57:]
            if patients_name:
                log[patients_name] = alias
            else:
                print('No "Patient\'s Name" found in {}/DICOMDIR'.format(d))
        return log

    @staticmethod
    def anonymize_log(conv_log, patient_log):
        """
        This method anonymizes a 'conversion log.txt' (generated by the Converter class) replacing
        the patient's names with their respective aliases, according to a patient log
        This file looks for a line containing: PATIENT INFO and then searches all subsequent
        lines to find a patient's real name. If it does then it replaces it and searches for the
        next instance of PATIENT INFO
        :param conv_log: A path to a conversion_log.txt (string)
        :param patient_log: A path to a patient log (string)
        :return: True
        """
        if not os.path.exists(conv_log):
            raise OSError('Invalid path: conversion log doesn\'t exist')
        if not os.path.exists(patient_log):
            raise OSError('Invalid path: patient log doesn\'t exist')
        pat_dct = {}
        print('Loading patient logs...')
        with open(patient_log, 'rb') as f:
            for line in f:
                pat_dct[line[:40].strip()] = line[40:].strip()
        print('Anonymizing conversion logs...')
        with open(conv_log, 'rb') as rf:
            filename = conv_log[:-4] + '_anon.txt'
            with open(filename, 'wb') as wf:
                expect_patient = False
                for line in rf:
                    if 'PATIENT INFO' in line:
                        expect_patient = True
                    if expect_patient:
                        for name in pat_dct.keys():
                            if name in line:
                                line = line.replace(name[:-1], pat_dct[name])
                                print('Replaced {} with {}'.format(name[:-1], pat_dct[name]))
                                expect_patient = False
                    wf.write(line)
        print('Anonymized log file stored in: {}'.format(filename))
        return True

    def get_results(self):
        """
        Method used for retrieving anonymization stats for logging or summarization purposes.
        :return: How many patients previously existed in the dictionary and how many exist now. (int, int)
        """
        return self.previous_entries, len(self.dct)

    @staticmethod
    def read_diction(diction_path=None):
        """
        Function that reads an anonymizer dictionary and returns a string with the contents of it for printing

        :param diction_path: A path to an anonymizer_dictionary.pkl (string).
        :return: A sting containing a printable version of the contents of the dictionary (string).
        """
        dct = pkl.load(open(diction_path, 'rb'))
        response = 'printing contents of: {}:\n'.format(diction_path)
        response += ' '+'-'*71+' \n'
        response += '| {:^3} | {:^50} | {:^10} |\n'.format('No.', 'Patient\'s Name', 'Alias')
        response += '| {:<3} | {:<50} | {:<10} |\n'.format('-'*3, '-'*50, '-'*10)
        for i, d in enumerate(dct.keys()):
            response += '| {:<3} | {:<50} | {:<10} |\n'.format(str(i+1)+'.', d, dct[d])
        response += ' '+'-'*71+' '
        return response


if __name__ == '__main__':
    assert len(sys.argv) == 2, "Too many arguments. Enter just one argument." if len(sys.argv) > 1 \
        else "Too few arguments. DICOM root path required as an argument."
    dcm_path = sys.argv[1]
    assert os.path.exists(dcm_path), "The path you entered is not valid."
    dicom_dirs = [dr for dr in os.listdir(dcm_path) if os.path.isdir(dr)]
    anon = Anonymizer(paths=dicom_dirs, verbose=True, run=True, similarity_check=False)
