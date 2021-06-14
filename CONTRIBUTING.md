# Extending **carbontracker**

## Carbon intensity APIs

**carbontracker** relies on APIs to query real-time local carbon intensities in the region in which you are training. These APIs are implemented in **carbontracker** as a [fetcher](https://github.com/lfwa/carbontracker/blob/master/carbontracker/emissions/intensity/fetcher.py).

We use [geocoder](https://github.com/DenisCarriere/geocoder) to fetch information based on the IP of the hardware executing the workload. The information retrieved from `geocoder.ip("me")` is supplied to the fetcher in the `g_location` object. More information about the geocoder is available [here](https://geocoder.readthedocs.io/).

If you wish to add your own `fetcher` to retrieve accurate carbon emissions from your region then you can do so by implementing an API through these simple steps:

1. Find an API which contains the carbon intensity values for your region. (Example: https://carbonintensity.org.uk/)
2. Add a new `fetcher` to the [existing folder](https://github.com/lfwa/carbontracker/tree/master/carbontracker/emissions/intensity/fetchers).
3. Inherit the [fetcher](https://github.com/lfwa/carbontracker/blob/master/carbontracker/emissions/intensity/fetcher.py) abstract class and implement the functions.
4. Add the class constructor to the list of working APIs in [`intensity.py`](https://github.com/lfwa/carbontracker/blob/master/carbontracker/emissions/intensity/intensity.py#L42) file. This is the `fetchers` list found in the `carbon_intensity` function.

The current available `fetchers` can be found [here](https://github.com/lfwa/carbontracker/tree/master/carbontracker/emissions/intensity/fetchers) and can serve as examples on how to implement a `fetcher`.

Help improve **carbontracker** and create a pull request with your working APIs!

## Component energy readings

It is also possible to add new component frameworks for measuring energy usage. In the base version of **carbontracker** NVIDIA GPUs and Intel CPUs are supported. Adding more is possible by inheriting [`handler`](https://github.com/lfwa/carbontracker/blob/master/carbontracker/components/handler.py).

*Work in progress*
