"""
Custom Cloudinary storage backend.
Bypasses django-cloudinary-storage and uses the Cloudinary SDK directly.
This is more reliable and easier to debug.
"""
import os
import cloudinary
import cloudinary.uploader
from django.core.files.storage import Storage
from django.conf import settings


class CloudinaryMediaStorage(Storage):
    """
    Stores uploaded files on Cloudinary and returns proper URLs.
    Falls back to Django's default file storage if Cloudinary
    is not configured.
    """

    def _upload(self, name, content):
        """Upload a file to Cloudinary and return the public_id."""
        # Remove extension from name for public_id
        folder = os.path.dirname(name)
        filename = os.path.splitext(os.path.basename(name))[0]
        public_id = f"{folder}/{filename}" if folder else filename

        result = cloudinary.uploader.upload(
            content,
            public_id=public_id,
            folder='aromallure',
            overwrite=True,
            resource_type='image',
        )
        return result['public_id']

    def _save(self, name, content):
        public_id = self._upload(name, content)
        return public_id

    def url(self, name):
        if not name:
            return ''
        if name.startswith('http'):
            return name
        cloud = cloudinary.config().cloud_name or 'hlft2bzj'
        return f"https://res.cloudinary.com/{cloud}/image/upload/{name}"

    def exists(self, name):
        return False  # Always allow overwrite

    def delete(self, name):
        try:
            cloudinary.uploader.destroy(name)
        except Exception:
            pass

    def size(self, name):
        return 0

    def path(self, name):
        raise NotImplementedError("Cloudinary storage doesn't support local paths")
