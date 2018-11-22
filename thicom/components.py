from __future__ import division
from contextlib import contextmanager
from tqdm import tqdm
import magic
import sys
import os

def is_dicom(dcm, same_size=False):
    """
    Function that checks if a file is a DICOM image. Can also check an iterable of paths to files
    for the same thing. Uses python's magic library. Raises an OSError if dcm is an invalid path.
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
    if isinstance(dcm, str):
        if not os.path.exists(dcm):
            raise OSError('Invalid path: {}. No such file.'.format(dcm))
        try:
            if "dicom" in magic.from_file(dcm).lower() and 'dicomdir' not in dcm.lower():
                return True
        # Error occures if dcm is a directory
        except IOError:
            pass
        # Return False either if dcm is a directory or if it failed the previous if clause
        return False
    else:
        ls = []
        for d in dcm:
            if os.path.exists(d):
                if "dicom" in magic.from_file(d).lower() and d.lower() not in 'dicomdir':
                    ls.append(True)
                else:
                    ls.append(False)
            else:
                print('Invalid path: {}. No such file. Skipping to next one.'.format(d))
                ls.append(None)
        return ls if same_size else all(ls)


def find_dcm(pts='.', verbose=False):
    """
    Returns a list of all DICOM images under a certain directory or list of directories.
    Excludes DICOMDIR files from the search. This Function utilizes os.walk and python's magic
    package.
    :param pts: Path to a directory under which the module will search (string),
                or a list of such paths (list of strings).
    :param verbose: True to print each directory it's looking in (bool).
    :return: A list of paths to dicom images - excluding DICOMDIR files (list of strings).
    """
    if isinstance(pts, str):
        if not os.path.exists(pts):
            raise OSError('Invalid path: {}.'.format(pts))
        if is_dicom(dcm=pts):
            return [pts]
        # if input points to a DICOMDIR file search under it
        elif 'dicomdir' in pts.lower():
            return find_dcm(os.path.split(pts)[0])
        else:
            if not os.path.isdir(pts):
                raise TypeError('{} is not a valid DICOM file.'.format(pts))
        pts = [pts]
    lst = []
    print('Searching for DICOM images...')
    try:
        for pt in pts:
            if verbose: print('Searching in directory:')
            if os.path.exists(pt):
                for directory, _, file_lst in os.walk(pt):
                    if verbose: print(directory)
                    for filename in file_lst:
                        f = os.path.join(os.path.abspath(directory), filename)
                        if is_dicom(f):
                            lst.append(f)
            else:
                if verbose: print('Invalid path {}.\nSkipping to next one'.format(pt))
    except KeyboardInterrupt:
        pass
    print('Found a total of {} DICOM images.'.format(len(lst)))
    return lst


def find_dcmdir(pts='.', verbose=False):
    """
    Returns a list of all DICOMDIR files under a certain directory or list of directories.
    :param pts: Path to a directory under which the module will search (string),
                or a list of such paths (list of strings).
    :param verbose: True to print each directory it's looking in (bool).
    :return: A list of paths to DICOMDIR files (list of strings).
    """
    lst = []
    if isinstance(pts, str):
        if not os.path.exists(pts):
            raise OSError('Invalid path: {}'.format(pts))
        pts = [pts]
    print('Searching for DICOMDIR files...')
    try:
        for pt in pts:
            if verbose: print('Searching in directory:')
            if os.path.exists(pt):
                for directory, _, file_lst in os.walk(pt):
                    if verbose: print(directory)
                    for filename in file_lst:
                        if filename == 'DICOMDIR':
                            lst.append(os.path.abspath(directory))
                            if verbose: print('Found DICOMDIR in directory: {}'.format(directory))
            else:
                if verbose: print('Invalid path {}.\nSkipping to next one'.format(pt))
    except KeyboardInterrupt:
        pass
    print('Found a total of {} DICOMDIR files.'.format(len(lst)))
    return lst


def find_png(pts='.', verbose=False, contains=None):
    """
    Returns a list of all png images under a certain directory or list of directories. User can choose to filter results
    that contain a certain string.
    :param pts: Path to a directory under which the module will search (string),
                or a list of such paths (list of strings).
    :param verbose: True to print each directory it's looking in (bool).
    :param contains: A string to filter results by (string).
    :return: A list of paths to png images possibly filtered by a string (list of strings).
    """
    if isinstance(pts, str):
        if not os.path.isdir(pts):
            raise OSError('Invalid path: {}'.format(pts))
        pts = [pts]
    lst = []
    if verbose: print('Searching for png images...')
    try:
        for pt in pts:
            if verbose: print('Searching in directory:')
            if os.path.exists(pt):
                for directory, _, file_lst in os.walk(pt):
                    if verbose: print(directory)
                    for filename in file_lst:
                        if filename.endswith('.png'):
                            if contains:
                                if contains.lower() in filename.lower():
                                    lst.append(os.path.join(os.path.abspath(directory), filename))
                            else:
                                lst.append(os.path.join(os.path.abspath(directory), filename))
            else:
                if verbose: print('Invalid path {}.\nSkipping to next one'.format(pt))
    except KeyboardInterrupt:
        pass
    if verbose: print('Found a total of {} png images.'.format(len(lst)))
    return lst


def find_all(pts='.', verbose=False):
    """
    This function searches and returns all DICOM files from a given path (or list of paths)
    To avoid walking through directories two times, it doesn't make use of functions find_dcm,
    find_dcmdir.
    :param pts: A path or a list of paths (string/list of strings)
    :param verbose: True to print each directory it's looking in and the images it found (bool).
    :return: Two lists with the absolute paths of the dicom images and dicomdir files respectively.
             (list, list)
    """
    imgs = []
    dirs = []
    if isinstance(pts, str):
        if not os.path.exists(pts):
            raise OSError('Invalid path.')
        pts = [pts]
    print('Searching for all associated DICOM files...')
    try:
        for pt in pts:
            if verbose: print('Searching in directory:')
            if os.path.exists(pt):
                for directory, _, file_lst in os.walk(pt):
                    if verbose: print(directory)
                    for filename in file_lst:
                        f = os.path.join(os.path.abspath(directory), filename)
                        if "dicom" in magic.from_file(f).lower():
                            if filename == 'DICOMDIR':
                                dirs.append(f)
                                if verbose: print('Found DICOMDIR in directory: {}'.format(directory))
                            else:
                                imgs.append(f)
                                if verbose: print('Found DICOM image in directory: {}'.format(directory))
            else:
                if verbose: print('Invalid path {}.\nSkipping to next one'.format(pt))
    except KeyboardInterrupt:
        pass
    print('Found a total of {} DICOMDIR files.'.format(len(dirs)))
    print('Found a total of {} DICOM images.'.format(len(imgs)))
    return imgs, dirs


def check_depth(dirs_to_check, normal_depth=2, relative=True):
    """
    This function checks the depth of a DICOMDIR file in a directory.
    e.g:
    >>> dicomdirs = ['NPD/Patient1/DICOMDIR', 'PD/Patient2/DICOMDIR', 'PD/Patient3/MRI/DICOMDIR']
    >>> print(check_depth(dicomdirs))
    ['PD/Patient3/MRI/DICOMDIR']

    :param dirs_to_check: A list of DICOMDIR paths (list).
    :param normal_depth:  A number indicating the normal depth of the DICOMDIR file (int).
    :param relative: True if we want to use relative or absolute depths (bool).
    :return: A list of DICOMDIR paths that don't have a depth equal to the normal_depth (list).
    """
    misses = []
    for d in dirs_to_check:
        rd = os.path.relpath(d) if relative else d
        if rd.count('/') != normal_depth:
            misses.append(d)
    return misses


def average_depth(list_of_dirs, relative=True):
    """
    Returns the average depth of a list of directories.
    e.g.
    >>> dicomdirs = ['./short/path/to/dicomdir', './a/longer/path/to/a/dicomdir', './an/even/longer/path/to/a/dicomdir']
    >>> print('Average depth:', average_depth(dicomdirs))
    # Average depth: 4.66666666667

    :param list_of_dirs: A list of directories to check (list).
    :param relative: True if user wants relative depth (bool).
    :return: The average depth of the directories (float).
    """
    if relative:
        list_of_dirs = map(os.path.relpath, list_of_dirs)
    depths = [os.path.relpath(d).count('/') for d in list_of_dirs]
    return sum(depths)/len(depths)


@contextmanager
def suppress_stdout():
    """
    Function for 'with' statement context managers. It is meant to suppress the output of anything inside the statement.
    e.g:
    >>> print('1')
    >>> with suppress_stdout():
    >>>    print('2')
    >>> print('3')
    1
    3
    """
    with open(os.devnull, 'w') as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


@contextmanager
def redirect_to_tqdm():
    """
    Function for 'with' statement context managers. Redirects stdout to tqdm.
    Usage:
    >>> with redirect_to_tqdm() as stdout:
    >>>     for _ in tqdm(range(10)):
    >>>         print('Something')
    Output will not ruin the progress bar.
    """
    save_stdout = sys.stdout
    try:
        sys.stdout = DummyTqdmFile(sys.stdout)
        yield save_stdout
    # Relay exceptions
    except Exception as exc:
        raise exc
    # Always restore sys.stdout if necessary
    finally:
        sys.stdout = save_stdout


class DummyTqdmFile(object):
    """
    Dummy file-like that will write to tqdm
    """
    a_file = None

    def __init__(self, a_file):
        self.a_file = a_file

    def write(self, x):
        # Avoid print() second call (useless \n)
        if len(x.rstrip()) > 0:
            tqdm.write(x, file=self.a_file)
