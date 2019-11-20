#!/usr/bin/env python
#
# Copyright 2019 Flavio Garcia
# Copyright 2016-2017 Veeti Paananen under MIT License
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Account registration.
"""

import logging
import os

from .account import Account
from .acme import Acme
from .errors import AutomatoesError, AccountAlreadyExistsError
from .crypto import (
    generate_rsa_key,
    load_private_key,
)
from .helpers import confirm

logger = logging.getLogger(__name__)


def register(server, account_path, email, key_file):
    # Don't overwrite silently
    if os.path.exists(account_path):
        if not confirm("The account file {} already exists. Continuing will"
                       " overwrite it with the new key."
                       " Continue?".format(account_path), default=False):
            raise AutomatoesError("Aborting.")

    # Confirm e-mail
    if not confirm("You're about to register a new account with the e-mail "
                   "{}. Continue?".format(email)):
        raise AutomatoesError("Aborting.")

    # Load key or generate
    if key_file:
        try:
            with open(key_file, 'rb') as f:
                account = Account(key=load_private_key(f.read()))
        except (ValueError, AttributeError, TypeError, IOError) as e:
            logger.error("Couldn't read key.")
            raise AutomatoesError(e)
    else:
        logger.info("Generating a new account key. This might take a second.")
        account = Account(key=generate_rsa_key(4096))
        logger.info("Key generated.")

    # Register
    acme = Acme(server, account)
    logger.info("Registering...")
    try:
        registration = acme.register(email)

        # If the server has terms of service, prompt the user to confirm
        # TODO: This is a really stupid flow. Keep an eye out on this issue:
        # https://github.com/ietf-wg-acme/acme/issues/59 and hope they fix it.
        if registration.terms:
            logger.info("This server requires you to agree to these terms:")
            logger.info("  {}".format(registration.terms))
            if not confirm("Agreed?"):
                logger.error("Aborting. Your account was still created, but it"
                             " won't be usable before agreeing to terms.")
                raise AutomatoesError()
            acme.update_registration({'agreement': registration.terms})
            logger.info("Updated account with agreement.")

        logger.info("Account {} created.".format(account.uri))
    except IOError as e:
        logger.error("Registration failed due to a connection or request "
                     "error.")
        raise AutomatoesError(e)

    # Write account
    directory = os.path.dirname(os.path.abspath(account_path))
    os.makedirs(directory, exist_ok=True)
    with open(account_path, 'wb') as f:
        os.chmod(account_path, 0o600)
        f.write(account.serialize())

    logger.info("Wrote account to {}.".format(account_path))
    logger.info("")
    logger.info("What next? Verify your domains with 'authorize' and use "
                "'issue' to get new certificates.")
