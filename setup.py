import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

with open("README.md") as f:
    readme = f.read()

about = {}
with open(os.path.join(here, "carbontracker", "__version__.py")) as f:
    exec(f.read(), about)

setup(name=about["__title__"],
      version=about["__version__"],
      description=about["__description__"],
      long_description=readme,
      long_description_content_type='text/markdown',
      author=about["__author__"],
      url=about["__url__"],
      license=about["__license__"],
      packages=find_packages(exclude=('tests', 'docs')),
      include_package_data=True,
      install_requires=[
          "geocoder",
          "numpy",
          "pandas",
          "requests",
          "pynvml",
          "psutil",
      ],
      python_requires=">=3.6")
