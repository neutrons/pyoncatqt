.. _sample:

Sample Usage
============

ONCatLogin Widget
-----------------
The following is a simple example of how to use the ONCatLogin widget in a PyQt application.
This example creates a main window with an ONCatLogin widget and two QListWidgets to display
the instrument lists for the SNS and HFIR facilities. The instrument lists are updated when
the connection status changes.
The only required argument for the ``ONCatLogin`` widget is the client ID. The client ID is a unique identifier
for the application that is used to authenticate with the ONCat server. The client ID is provided by the ONCat support team
and should exist in pyoncatqt configuration file.

Authentication uses a browser-based sign-in (the OAuth Device Authorization Grant). When the user clicks the
login button, the widget starts an interactive sign-in on a worker thread and shows a small dialog with a link.
The user opens that link in a browser and approves the sign-in with their ORNL credentials. No username or
password is entered inside the application. Once the sign-in resolves, the widget refreshes its connection
status and emits ``connection_updated``.

.. literalinclude:: sample_usage.py


Configuration: ``key`` and ``client_id``
-----------------------------------------

The ``ONCatLogin`` widget creates and owns its ``pyoncat.ONCat`` agent for you, so you do not
need to build one yourself. It accepts either a ``key`` or a ``client_id``:

- If ``key`` (an application name) is passed, the client ID is looked up from the pyoncatqt
  configuration file, provided an entry exists for it.
- If ``client_id`` is passed, it is used directly.
- If both are passed, ``client_id`` configures the agent while ``key`` still names the token file.

Without ``key``, the token filename uses the client-ID prefix; with ``key``, it uses the key.
The token is stored under ``~/.pyoncatqt/``.

Browser-Based Sign-In (Device Authorization Grant)
--------------------------------------------------

The widget authenticates using the OAuth Device Authorization Grant. There is no username or
password field: the user approves the sign-in in a browser instead. The widget builds its agent
with ``flow=pyoncat.DEVICE_AUTHORIZATION_FLOW`` and wires the token storage callbacks, roughly
as follows:

.. code:: python

    import pyoncat

    ONCAT_URL = "https://oncat.ornl.gov"

    agent = pyoncat.ONCat(
        ONCAT_URL,
        client_id=CLIENT_ID,
        flow=pyoncat.DEVICE_AUTHORIZATION_FLOW,
        scopes=["api:read"],
        token_getter=read_token,
        token_setter=write_token,
        # Raise InteractionRequiredError on a dead session instead of
        # silently re-prompting from inside a data call.
        reauth_on_expired=pyoncat.REAUTH_INTERACTION_REQUIRED,
        verification_handler=verification_handler,
    )

When the login button is clicked, the widget:

1. Checks for an existing, valid stored session. If one is present, it simply refreshes the
   connection status and does nothing further.
2. Otherwise clears any stale token and starts ``agent.login()`` on a worker thread. Because
   ``login()`` blocks while it polls the identity provider, it must not run on the GUI thread.
3. Receives the device-authorization challenge (verification link and one-time code) from
   PyONCat via the ``verification_handler`` and shows a small dialog with a clickable link.
   The user opens the link in a browser and approves the sign-in with their ORNL credentials.
4. On success, closes the dialog, refreshes the connection status, and emits
   ``connection_updated``. If the user cancels, the poll loop is aborted cleanly.

Customizing the sign-in dialog title
-------------------------------------

Pass ``login_title`` to override the title of the sign-in dialog window (it defaults to
``"Sign in to ONCat"``):

.. code:: python

    self.oncat_widget = ONCatLogin(key="client", login_title="Connect to ONCat", parent=self)
