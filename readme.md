\# napari-autofill-contours



\[!\[License](https://img.shields.io/pypi/l/napari-autofill-contours.svg?color=green)](https://github.com/podtyazhki1337/napari-autofill-contours/raw/main/LICENSE)

\[!\[PyPI](https://img.shields.io/pypi/v/napari-autofill-contours.svg?color=green)](https://pypi.org/project/napari-autofill-contours)

\[!\[Python Version](https://img.shields.io/pypi/pyversions/napari-autofill-contours.svg?color=green)](https://python.org)

\[!\[napari hub](https://img.shields.io/endpoint?url=https://api.napari-hub.org/shields/napari-autofill-contours)](https://napari-hub.org/plugins/napari-autofill-contours)



A napari plugin for automatic filling of regions from contour masks.



---

\## Why use this plugin?



When working with segmented images, you often have \*\*contours drawn around objects\*\* but need \*\*filled masks\*\* for further analysis. Manually filling each contour is tedious and time-consuming.



\*\*This plugin solves that problem by:\*\*

\- Automatically detecting and filling all closed regions inside contours

\- Preserving the original label IDs and colors from your contours

\- Intelligently distinguishing between object interiors and background areas

\- Handling overlapping or touching contours without merging them into single objects



\*\*Perfect for:\*\*

\- Converting hand-drawn or AI-generated contours into solid masks

\- Post-processing segmentation results

\- Preparing masks for quantitative analysis (area, intensity measurements, etc.)

\- Cell biology, histology, and microscopy image analysis



\## Features



\- ✅ Auto-fills closed regions inside contours

\- 🎨 Preserves original label IDs and colors

\- 🧠 Smart background detection

\- 🔧 Configurable parameters

\- 📊 Supports both Image and Labels layers

\- 🚫 Prevents creating more objects than unique labels



---



\## Installation



```bash

pip install napari-autofill-contours

```



Or install latest development version:



```bash

pip install git+https://github.com/podtyazhki1337/napari-autofill-contours.git

```



---



\## Usage



1\. Open napari

2\. Load a layer with contours (Image or Labels)

3\. Open plugin: `Plugins → napari-autofill-contours → Auto-Fill Contours`

4\. Adjust parameters if needed

5\. Click `Run Auto-Fill`



\### Parameters



| Parameter | Description | Default |

|-----------|-------------|---------|

| \*\*Source layer\*\* | Layer with contours | - |

| \*\*Force non-black as lines\*\* | Treat all non-black pixels as contours | False |

| \*\*Otsu bias (+)\*\* | Otsu threshold adjustment (0-40) | 5 |

| \*\*Line closing (iters)\*\* | Iterations for closing gaps (0-10) | 2 |

| \*\*Min area (px)\*\* | Minimum object area in pixels | 11 |

| \*\*Background threshold\*\* | Neighbor count for background detection (2-10) | 5 |



---



\## Requirements



\- Python >= 3.8

\- napari >= 0.4.0

\- numpy

\- scikit-image >= 0.19.0

\- scipy

\- magicgui



---



\## Contributing



Contributions are welcome! Please feel free to submit a Pull Request.



---



\## License



Distributed under the terms of the \[MIT] license.



---



\## Issues



If you encounter any problems, please \[file an issue] with a detailed description.



\[MIT]: http://opensource.org/licenses/MIT

\[napari]: https://github.com/napari/napari

\[file an issue]: https://github.com/podtyazhki1337/napari-autofill-contours/issues

