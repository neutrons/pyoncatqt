.. Purpose: The root document of the project, which serves as welcome page and contains the root
.. of the "table of contents tree" (or toctree).

PyONCatQt Documentation
=======================

PyONCatQt is a Python package designed to provide a Qt-based GUI for authentication
and connection to the ONCat service, a data cataloging and management system developed
by Oak Ridge National Laboratory. It serves as a plugin for other applications,
offering a convenient PyQt-based GUI component,
ONCatLoginDialog, for securely inputting login credentials. Upon successful authentication,
the package establishes a connection to the ONCat service, granting access to various data
management functionalities. PyONCatQt aims to streamline the login process and enhance user
experience when interacting with ONCat within Python applications.

Getting Started
---------------
To install PyONCatQt, run the following command:

.. code-block:: bash

   conda install -c neutrons pyoncatqt

To use PyONCatQt please see the :ref:`sample` section for examples.

Contents
--------

.. toctree::
   :maxdepth: 1

   source/reference
   source/sample
