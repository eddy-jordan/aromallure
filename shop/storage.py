"""
Custom Cloudinary storage backend with detailed logging.
"""
import os
import logging
import cloudinary
import cloudinary.uploader
from django.core.files.storage import Storage

logger = logging.getLogger(__name__)


class CloudinaryMediaStorage(Storage):

    def _save(self, name, content):
        logger.warning(f"CloudinaryMediaStorage._save called: {name}")
        try:
            folder   = os.path.dirname(name)
            filename = os.path.splitext(os.path.basename(name))[0]
            public_id = f"aromallure/{folder}/{filename}" if folder else f"aromallure/{filename}"

            logger.warning(f"Uploading to Cloudinary public_id: {public_id}")
            logger.warning(f"Cloudinary cloud_name: {cloudinary.config().cloud_name}")
            logger.warning(f"Cloudinary api_key set: {bool(cloudinary.config().api_key)}")

            result = cloudinary.uploader.upload(
                content,
                public_id=public_id,
                overwrite=True,
                resource_type='image',
            )
            logger.warning(f"Upload SUCCESS: {result['secure_url']}")
            return result['public_id']
        except Exception as e:
            logger.warning(f"Upload FAILED: {type(e).__name__}: {e}")
            raise

    def url(self, name):
        if not name:
            return ''
        if name.startswith('http'):
            return name
        cloud = cloudinary.config().cloud_name or 'hlft2bzj'
        return f"https://res.cloudinary.com/{cloud}/image/upload/{name}"

    def exists(self, name):
        return False

    def delete(self, name):
        try:
            cloudinary.uploader.destroy(name)
        except Exception:
            pass

    def size(self, name):
        return 0

    def path(self, name):
        raise NotImplementedError("Cloudinary storage doesn't support local paths")
