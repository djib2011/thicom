from __future__ import print_function, division
from tqdm import tqdm
import numpy as np
import sys
import os

if sys.version[0] == '2': input = raw_input


class Combine:

    def __init__(self, parent_dir='.', window=3, ratio=0.75, verbose=False, inter_patient_combinations=True, save=False,
                 save_directory=None):
        """
        This class is meant to be used for generating a training and test set from a series of Dat scan and MRI images.
        First all MRIs and Dat scans are gathered, separately for positive and negative patients. MRIs from different
        patients are separated by '-------------'. Then a sliding window technique is applied to the MRIs as shown in
        the following example (for a window size of 3):

        Before the application of the window:
        MRIs = [1.png, 2.png, 3.png, 4.png, 5.png, 6.png, '-------------', 11.png, 12.png, 13.png, 14.png]
        After the application of the window:
        [1.png, 2.png, 3.png, 4.png, 2.png, 3.png, 4.png, 3.png, 4.png, 5.png, 4.png, 5.png, 6.png, 11.png, 12.png,
        13.png,12.png, 13.png, 14.png]

        Note that windows do overlap but NOT over separate patients!

        After applying the window to the MRIs, each of those windows is combined to a different Dat scan. All possible
        combinations are generated; positive and negative patients are NOT mixed together.

        Finally the data is split into a training and test set according to a given ratio and shuffled through
        numpy.random.

        :param parent_dir: Where to start the search from (str).
        :param window: Size of the window to be applied to the MRIs (int).
        :param ratio: training examples / (training + testing) examples (float).
        :param inter_patient_combinations: False if user wants only intra-patient combinations,
                                           True for also allowing inter-patient combinations (bool)
        :param verbose: True/False whether or not user wants his screen flooded with messages (bool).
        :param save: True/False whether or not user wants to store the generated training and test sets (bool).
        :param save_directory: Directory indicating where to store the files containing the training and test sets (str)
        """

        self.parent_dir = os.path.abspath(parent_dir)
        self.verbose = verbose
        self.window = window
        if not save_directory: save_directory = parent_dir

        pd_cmb, npd_cmb = self.generate_combinations(inter=inter_patient_combinations)
        self.npd = self.shuffle(npd_cmb)
        self.pd = self.shuffle(pd_cmb)

        # calculate exact split points
        npd_sp = int(len(npd_cmb) * ratio // 4 * 4)
        pd_sp = int(len(pd_cmb) * ratio // 4 * 4)
        print('Exact split ratios are:\nPD: {:.5f}\nNPD: {:.5f}'.format(npd_sp/len(npd_cmb), pd_sp/len(pd_cmb)))

        # split the data into a training and test set
        npd_train, npd_test = npd_cmb[:npd_sp], npd_cmb[npd_sp:]
        pd_train, pd_test = pd_cmb[:pd_sp], pd_cmb[pd_sp:]

        del pd_cmb, npd_cmb

        # shuffle the data
        self.train = self.shuffle(npd_train + pd_train)
        self.test = self.shuffle(npd_test + pd_test)

        del npd_train, npd_test, pd_train, pd_test

        # save to a file
        if save:
            print('Saving combinations in directory: {}'.format(save_directory))
            with open(os.path.join(save_directory, 'train.txt'), 'wb') as f:
                for ln in self.train:
                    f.write(ln + '\n')
            with open(os.path.join(save_directory, 'test.txt'), 'wb') as f:
                for ln in self.test:
                    f.write(ln + '\n')

    def generate_combinations(self, parent_dir=None, inter=True):
        """
        Basic function that generates all possible combinations from the patients' images. Allows inter-patient
        combinations, if desired.

        :param parent_dir: Where to start the search from (str).
        :param inter: False if user wants only intra-patient combinations, True for also allowing inter-patient
                      combinations (bool)
        :return:
        """
        if not parent_dir: parent_dir = self.parent_dir

        npd_dir, pd_dir = self.find_directories(parent_dir=parent_dir)

        if inter:

            npd_dat, npd_mri = self.structured_search(npd_dir)
            pd_dat, pd_mri = self.structured_search(pd_dir)

            print('{:^15}{:^15}{:^15}{:^15}'.format('NPD datscans', 'NPD MRIs', 'PD datscans', 'PD MRIs'))
            print('{:^15}{:^15}{:^15}{:^15}'.format(len(npd_dat), len(npd_mri), len(pd_dat), len(pd_mri)))

            # repeat and group the MRIs according to a pre-specified window
            final_npd_mri = self.group_mri(npd_mri)
            final_pd_mri = self.group_mri(pd_mri)

            # print summary and expectations
            print('\nTotal number of MRI images (NPD, PD):')
            print('{:^15}{:^15}'.format(len(final_npd_mri), len(final_pd_mri)))
            print('Total number of MRI bundles (NPD, PD):')
            print('{:^15}{:^15}\n'.format(len(final_npd_mri)//self.window, len(final_pd_mri)//self.window))
            print('Expected NPD Bundles: {} * {} = {}'.format(len(final_npd_mri)//self.window, len(npd_dat),
                                                              len(final_npd_mri)//self.window * len(npd_dat)))
            print('Expected PD Bundles: {} * {} = {}\n'.format(len(final_pd_mri)//self.window, len(pd_dat),
                                                               len(final_pd_mri)//self.window * len(pd_dat)))

            # generate all possible dat-to-MRI_window combinations
            npd_cmb = self.combinations(final_npd_mri, npd_dat, label=0)
            pd_cmb = self.combinations(final_pd_mri, pd_dat, label=1)

        else:
            npd_images = self.structured_search(npd_dir, inter=False)
            pd_images = self.structured_search(pd_dir, inter=False)

            npd_cmb, pd_cmb = [], []
            for p in tqdm(npd_images):
                if len(npd_images[str(p)]['dat']) > 0 and len(npd_images[str(p)]['mri']) > 0:
                    npd_cmb += self.combinations(npd_images[str(p)]['mri'], npd_images[str(p)]['dat'], label=0)
            for p in tqdm(pd_images):
                if len(pd_images[str(p)]['dat']) > 0 and len(pd_images[str(p)]['mri']) > 0:
                    pd_cmb += self.combinations(pd_images[str(p)]['mri'], pd_images[str(p)]['dat'], label=1)

        # print results
        print('Total number of images (NPD, PD):')
        print('{:^15}{:^15}'.format(len(npd_cmb), len(pd_cmb)))
        print('Total number of bundles (NPD, PD):')
        print('{:^15}{:^15}\n'.format(int(len(npd_cmb)/(self.window+1)), int(len(pd_cmb)/(self.window+1))))
        rat = len(pd_cmb)/len(npd_cmb)
        print('Imbalance Ratio: 1:{:.2f}'.format(rat))
        print('NPD: {:.2f}%'.format(100/(rat+1)))
        print('PD:  {:.2f}%'.format(100*rat/(rat+1)))
        print()

        return pd_cmb, npd_cmb

    def structured_search(self, pt, inter=True):
        """
        Searches for dat scan and mri images under path 'pt' and stores them in separate lists. Finally these lists are
        sorted. Patient's MRIs are separated by '-------------'.
        :param pt: A path to act as a starting point for the search (str).
        :param inter: False for allowing only intra-patient combinations.
                      True for allowing inter-patient combinations (bool)
        :return: Two lists, one containing all dat scan images and one containing the MRIs (list, list)
        """
        dat = []
        mri = []
        images = {}
        if self.verbose: print('Looking for images under directory:\n{}'.format(pt))
        for directory, _, f in os.walk(pt):
            if self.verbose: print(directory)
            if not inter:
                if '0.dat' or '1.mri' in directory.lower():
                    # patient_id = ''.join(x for x in directory.split('/')[-2] if x.isdigit())
                    patient_id = ''.join(x for x in directory.split('/') if x.isdigit())
                    if patient_id not in images.keys():
                        images[patient_id] = {'dat': [], 'mri': []}
            for filename in f:
                os.rename(os.path.join(directory, filename), os.path.join(directory, n))
                filename = n
                if '0.dat' in directory.lower():
                    if inter:
                        dat.append(os.path.join(directory, filename))
                    else:
                        images[patient_id]['dat'].append(os.path.join(directory, filename))
                if '1.mri' in directory.lower():
                    tmp = '_'.join(filename.split('_')[:-1] + [filename.split('_')[-1]])
                    if inter:
                        mri.append(os.path.join(directory, tmp))
                    else:
                        images[patient_id]['mri'].append(os.path.join(directory, tmp))
            mri.append('-------------')
        if self.verbose and inter: print('{} DaT scan and {} MRI images found.'.format(len(dat), len(mri)))
        dat.sort()
        mri.sort()
        if inter:
            return dat, mri
        else:
            return images

    def find_directories(self, parent_dir=None):
        """
        Function used for finding the subdirectories for the PD and NPD subjects, under directory 'patient_dir'. User
        selects which directory is which.

        :param parent_dir: Directory under the subdirectories for PD and NPD subjects lie (str)
        :return: Two directories, for NPD and PD subjects respectively (str, str)
        """
        if not parent_dir: parent_dir = self.parent_dir

        diagnosis_dirs = [os.path.join(os.path.abspath(parent_dir), x) for x in os.listdir(parent_dir)
                          if (os.path.isdir(os.path.join(os.path.abspath(parent_dir), x)) and x[0] != '.')]
        if len(diagnosis_dirs) < 2:
            raise OSError('There should be at least two directories (positive/negative)')

        while True:
            for i, d in enumerate(diagnosis_dirs):
                print('{}. {}'.format(i, os.path.relpath(d)))
            inp = input('Which directories do you want to use? Negative directory first, Positive second,'
                        'space separated!\nIf format is already ok press (e.g. 0. NPD, 1. PD) press enter.'
                        '\nAny non numeric character will terminate.\n')
            if inp == '': return diagnosis_dirs
            inp = inp.split()
            if len(inp) != 2:
                if not ''.join(inp).isdigit():
                    sys.exit()
                print('Invalid input. Two space separated values are required. Try again.\n')
                continue
            try:
                for i in inp:
                    if not i.isdigit():
                        sys.exit()
                    if int(i) >= len(diagnosis_dirs) or int(i) < 0:
                        print('Invalid input: {}, try again.\n'.format(i))
                        raise ValueError

                return diagnosis_dirs[int(inp[0])], diagnosis_dirs[int(inp[1])]

            except ValueError:
                continue

    def group_mri(self, mri):
        """
        Groups MRI images according to a specified window. For example for a window of 3, and an MRI list of 6:
        [1.png, 2.png, 3.png, 4.png, 5.png, 6.png]
        we would receive a the following list:
        [1.png, 2.png, 3.png, 4.png, 2.png, 3.png, 4.png, 3.png, 4.png, 5.png, 4.png, 5.png, 6.png]
        :param mri: A list of MRIs, where the different patients are separated by '-------------' (list).
        :return: A list of MRIs grouped according to a specific window (list).
        """
        i = 0
        final_mri = []
        print(len(mri))
        while i+self.window-1 < len(mri):
            if '-------------' not in [mri[j] for j in range(i, i+self.window)]:
                for w in range(self.window):
                    final_mri.append(mri[i + w])
            i += 1
        if self.verbose:
            print('Created {} groups of {} from {} MRI images.'.format(len(final_mri), len(mri), self.window))
        return final_mri

    def combinations(self, mri, dat, label):
        """
        Generates all possible combinations of MRIs with dat scans with a given window. If the window size is N, then
        N MRIs are combined with 1 dat scan. Also assigns a label to each category
        :param mri: A list of MRIs (list).
        :param dat: A list of dat scans (list).
        :param label: A numerical or categorical label for the category.
        :return: A list of all possible MRI-DAT combinations (list).
        """
        cmb = []
        for i in range(0, len(mri)-self.window, self.window):
            for j in dat:
                for w in range(self.window):
                    cmb.append(mri[i + w] + ' ' + str(label))
                cmb.append(j + ' ' + str(label))
        return cmb

    def shuffle(self, data, size=None):
        """
        Shuffles a list by chunks. For example the list [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] with a chunk size of 3
        would be shuffled: [7, 8, 9, 1, 2, 3, 10, 11, 12, 4, 5, 6]
        :param data: A list.
        :param size: Size of each chunk (int)
        :return: A shuffled version of the previous list
        """
        if not size: size = self.window
        # convert the list to and array of shape (list_length/chunk_size, chunk_size)
        arr = np.array(data).reshape(int(len(data)/(size+1)), size+1)
        # shuffle the array (only the rows)
        np.random.permutation(arr)
        # reshape and cast the array as a list and return it
        return list(arr.reshape(len(data),))
