import logging
import os
import firebase_admin
from firebase_admin import auth, credentials, exceptions
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_firebase_app() -> firebase_admin.App:
    """
    Initializes and returns the singleton Firebase Admin App instance.
    Supports:
    1. Explicit service account JSON path via settings.FIREBASE_CREDENTIALS_PATH or GOOGLE_APPLICATION_CREDENTIALS.
    2. Google Cloud Application Default Credentials (ADC) in Cloud Run / GCP environments.
    3. Firebase Project ID if configured.
    """
    try:
        return firebase_admin.get_app()
    except ValueError:
        cred = None
        cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path and os.path.exists(cred_path):
            logger.info("Initializing Firebase Admin with service account file: %s", cred_path)
            cred = credentials.Certificate(cred_path)

        options = {}
        if settings.FIREBASE_PROJECT_ID:
            options["projectId"] = settings.FIREBASE_PROJECT_ID

        if cred:
            app = firebase_admin.initialize_app(cred, options=options if options else None)
        else:
            logger.info("Initializing Firebase Admin with default credentials")
            app = firebase_admin.initialize_app(options=options if options else None)

        logger.info("Firebase Admin initialized successfully")
        return app


def delete_firebase_user(uid: str) -> None:
    """
    Deletes the user from Firebase Authentication using the Admin SDK.
    If the user does not exist in Firebase (UserNotFoundError), it is treated as a success (idempotent).
    Raises an exception on any other failure so the calling database transaction can roll back.
    """
    get_firebase_app()
    try:
        auth.delete_user(uid)
        logger.info("Successfully deleted Firebase Auth user with UID: %s", uid)
    except auth.UserNotFoundError:
        logger.warning("User '%s' was not found in Firebase Auth; proceeding as already deleted.", uid)
