# thicom
### (thanos' DICOM package)

Simple manipulation of DICOM images. Wrapper to python's pydicom package. Intended for self-use.

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


## Quick Start

Import this package:

```python
import thicom
dcm = 'path/to/dicom/image.dcm'
pt = 'path/to/patients/parent/directory/'
```
- To view a DICOM image dcm:
```python
thicom.view(dcm)
```
- To view all DICOM images in the CWD as an animation:

```python
thicom.view()
```

- To decompress compressed all DICOM images under path `pt`:

```python
pt = 'images/dicom/'
thicom.decompress(pt)
```

- To convert all DICOM images under path `pt` to .png:

```python
thicom.to_png(pt)
```

- To anonymize all patients under path `pt`:

```python
thicom.anonymize(pt)
```

- To search for DICOM images, DICOMDIR or both under path `pt`:

```python
thicom.find_dcm(pt)    # looks for DICOM images
thicom.find_dcmdir(pt) # looks for DICOMDIR
thicom.find_all(pt)    # looks for all DICOM files
thicom.find_png(pt)    # looks for png images
```

- To check if files are in DICOM format:

```python
f = 'files/random_file'
thicom.is_dicom(f)
files = ['files/random_file1', 'files/random_file2', 'files/random_file3']
thicom.is_dicom(files)
# Will return True if all files are in DICOM format
thicom.is_dicom(files, same_size=True)
# Will return a list with the same size as files (e.g. [True, True, False])
```

- To check if the directory `pt` satisfies the requirements for processing:

```python
thicom.pre_check(pt)
```

- To process all files in the directory `pt` (will also perform a `pre_check`):

```python
thicom.preprocess(pt)
```

By default all functions use the CWD as their default argument.

## Requirements:

- numpy, scipy, matplotlib
- pydicom
- tqdm
- In case of compressed DICOM files:  
a linux distribution and the [GDCM](http://gdcm.sourceforge.net/wiki/index.php/Main_Page') package installed (`gdcmconv` tool)

## Module description:

1. `components`  
Module containing useful functions required bu multiple other modules in the package.
E.g. it contains functions that search a directory for *dicom* files and *png* images.

2. `anonymizer`  
This module handles mapping patients' real names with aliases and storing the map (called an *anonymizer dictionary*).
Has the option of updating a previously created map.

3. `decomp`   
Some *dicom* images are compressed through lossless-JPEG compression and can't be handled by python's dicom package.
This module uses linux's "gdcmconv" tool for decompressing the images.

4. `converter`  
`converter` handles converting one or more *dicom* images to *png* ones.
It preserves all useful metadata (besides of the patient's) name which is anonymized (through `anonymizer`).
It can handle *dicom* files storing multiple images and uses `decomp` to decompress compressed *dicom* files.
Besides saving the image, it can also show one or more *dicom* images to the screen.

5. `preprocess`  
Module that handles all necessary preprocessing steps to initialize or update a database of subjects.
First it performes a compatibility check to see if the directory has the desired structure. It searches for:  
*(a)* patients with DaT scans in *dicom* format (with a *DICOMDIR*)  
*(b)* patients without MRI *DICOMDIRs*  
*(c)* multiple MRI *DICOMDIRs* for a single patient  
*(d)* wrong directory structure (e.g `NPD/Patient/MRI/DICOMDIR` instead of `NPD/Patient/DICOMDIR`)  
*(e)* wrong directory name (`D.Patient`, `D1 Patient`, `D1a Patient`, etc.)  
Some of these issues can be fixed automatically. Afterwards it will create and apply an anonymization scheme 
(using `anonymizer`), convert all *DICOM* images to *png* (while generating all necessary log files) with `converter`,
structure the directories according to the scheme while removing any obsolete file. Then it searches for all MRIs 
containing `T1` in their name and stores them in a separate directory.  

6. `augment`  
This module is meant to be used for generating a training and test set from a series of Dat scan and MRI images.
First all MRIs and Dat scans are gathered, separately for positive and negative patients. MRIs from different
patients are separated by `'-------------'`. Then a sliding window technique is applied to the MRIs as shown in
the following example (for a window size of 3):  
    ```python
    # Before the application of the window:
    MRIs = [1.png, 2.png, 3.png, 4.png, 5.png, 6.png, '-------------', 11.png, 12.png, 13.png, 14.png]
    # After the application of the window:
    MRIs = [1.png, 2.png, 3.png, 4.png, 2.png, 3.png, 4.png, 3.png, 4.png, 5.png, 4.png, 5.png, 6.png, 11.png, 12.png,
            13.png,12.png, 13.png, 14.png]
    ```  
    Note that windows do overlap but **not** over separate patients!

    After applying the window to the MRIs, each of those windows is combined to a different DaT scan. All possible
    combinations are generated; PD and NPD patients are **not** mixed together.

    Finally the data is split into a training and test set according to a given ratio and shuffled through 
    `numpy.random`.

## Directory structure

Before processing the directories should have the following structure:
  
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

After preprocessing the directory will look like this:

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

## Associated publications:

- Tagaris, A., Kollias, D., Stafylopatis, A., Tagaris, G., & Kollias, S. (2018). Machine Learning for Neurodegenerative Disorder Diagnosis—Survey of Practices and Launch of Benchmark Dataset. International Journal on Artificial Intelligence Tools, 27(03), 1850011.
- Kollias, D., Tagaris, A., Stafylopatis, A., Kollias, S., & Tagaris, G. (2018). Deep neural architectures for prediction in healthcare. Complex & Intelligent Systems, 4(2), 119-131.
- Kollias, D., Yu, M., Tagaris, A., Leontidis, G., Stafylopatis, A., & Kollias, S. (2017, November). Adaptation and contextualization of deep neural network models. In Computational Intelligence (SSCI), 2017 IEEE Symposium Series on (pp. 1-8). IEEE.
- Vlachostergiou, A., Tagaris, A., Stafylopatis, A., & Kollias, S. (2018, October). Multi-Task Learning for Predicting Parkinson's Disease Based on Medical Imaging Information. In 2018 25th IEEE International Conference on Image Processing (ICIP) (pp. 2052-2056). IEEE.
- Vlachostergiou, A., Tagaris, A., Stafylopatis, A., & Kollias, S. (2018, October). Investigating the Best Performing Task Conditions of a Multi-Tasking Learning Model in Healthcare Using Convolutional Neural Networks: Evidence from a Parkinson'S Disease Database. In 2018 25th IEEE International Conference on Image Processing (ICIP) (pp. 2047-2051). IEEE.
