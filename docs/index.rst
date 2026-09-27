Contacts API documentation
==========================

REST API for storing contacts, built with FastAPI, SQLAlchemy (async),
PostgreSQL and Redis.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Application
-----------

.. automodule:: main

Configuration
-------------

.. automodule:: src.conf.config

Database
--------

.. automodule:: src.database.db

.. automodule:: src.database.models
   :exclude-members: metadata, registry

Schemas
-------

.. automodule:: src.schemas

Repository
----------

.. automodule:: src.repository.contacts

.. automodule:: src.repository.users

Services
--------

.. automodule:: src.services.auth

.. automodule:: src.services.cache

.. automodule:: src.services.users

.. automodule:: src.services.contacts

.. automodule:: src.services.email

.. automodule:: src.services.upload_file

.. automodule:: src.services.limiter

API routes
----------

.. automodule:: src.api.auth

.. automodule:: src.api.users

.. automodule:: src.api.contacts

.. automodule:: src.api.utils

Management
----------

.. automodule:: src.create_admin

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
