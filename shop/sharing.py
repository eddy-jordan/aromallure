"""
What a shared link looks like.

When someone pastes a link into WhatsApp, Instagram, Facebook, Telegram and so
on, the app fetches the page and reads its Open Graph tags to build the preview
card (photo, title, description). These helpers work out those values for
perfume pages and brand pages; base.html renders the tags.

Everything handed to the templates is an absolute URL, because the apps that
read the tags are not on our site and can't resolve a relative path.
"""
from django.conf import settings
from django.templatetags.static import static
from django.utils.text import Truncator

_CLOUDINARY_UPLOAD = '/image/upload/'


def absolute_url(request, url):
    """Make `url` absolute; leave it alone if it already is."""
    if not url:
        return ''
    if url.startswith(('http://', 'https://')):
        return url
    return request.build_absolute_uri(url)


def preview_image(url):
    """Cloudinary images get a 1200x630 JPEG version for link previews. The
    apps that build previews reject or skip very large files (WhatsApp is the
    strict one), and 1.91:1 is the shape they all display. Other URLs are used
    as they are. Set SHARE_PREVIEW_RESIZE=False in the environment to turn the
    resizing off (for example if the Cloudinary account blocks unsigned
    transformations)."""
    if not getattr(settings, 'SHARE_PREVIEW_RESIZE', True):
        return url
    if 'res.cloudinary.com' in url and _CLOUDINARY_UPLOAD in url:
        head, tail = url.split(_CLOUDINARY_UPLOAD, 1)
        return f'{head}{_CLOUDINARY_UPLOAD}c_fill,g_auto,w_1200,h_630,q_auto,f_jpg/{tail}'
    return url


def default_image(request):
    """The logo, used when a page has no better picture."""
    return request.build_absolute_uri(static('shop/img/logo-full.png'))


def _money(value):
    return f'{value:.2f}'


def product_share(request, product):
    """Preview and share-sheet values for one perfume page."""
    price = product.current_price
    site = getattr(settings, 'SITE_NAME', 'our store')

    facts = [product.get_concentration_display(), f'{product.volume_ml}ml', f'GH₵{_money(price)}']
    if product.scent_notes:
        facts.append(product.scent_notes)
    blurb = ' '.join((product.description or '').split())
    description = Truncator(' · '.join(facts) + ('. ' + blurb if blurb else '')).chars(200)

    text = f'Check out {product.name} by {product.brand} on {site}, GH₵{_money(price)}'
    if product.on_sale:
        text += f' (was GH₵{_money(product.price)})'

    raw_image = product.image_url
    if not raw_image and product.image:
        try:
            raw_image = product.image.url
        except Exception:
            raw_image = ''
    image = preview_image(absolute_url(request, raw_image)) if raw_image else ''

    return {
        'type': 'product',
        'title': f'{product.name} by {product.brand}',
        'description': description,
        'text': text,
        'url': request.build_absolute_uri(product.get_absolute_url()),
        'image': image,
        'image_alt': f'{product.name} by {product.brand}',
        'price': _money(price),
        'currency': 'GHS',
    }


def brand_share(request, brand, count):
    """Preview values for a brand page."""
    site = getattr(settings, 'SITE_NAME', 'our store')
    noun = 'fragrance' if count == 1 else 'fragrances'
    return {
        'type': 'website',
        'title': f"{brand['name']} fragrances",
        'description': f"Shop {count} {brand['name']} {noun} at {site}. Elegance in a bottle.",
        'url': request.build_absolute_uri(request.path),
    }
