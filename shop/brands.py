"""
Brand grouping for the "Shop by brand" strip and brand pages.

Brands are not a model: each product just stores its brand name. Names are
grouped by their slug, so "Dior", "dior" and "Dior " all land in one brand.
The most common spelling is the one shown to customers.
"""
from collections import Counter

from django.db.models import Count
from django.utils.text import slugify

from .models import Product


def _group(rows):
    groups = {}
    for row in rows:
        raw = row['brand']
        slug = slugify(raw)
        if not slug:
            continue  # nothing usable to put in a URL (e.g. only symbols)
        g = groups.setdefault(slug, {'slug': slug, 'count': 0, 'raw': [], 'spellings': Counter()})
        g['count'] += row['n']
        g['raw'].append(raw)
        g['spellings'][raw.strip()] += row['n']
    result = []
    for g in groups.values():
        g['name'] = g['spellings'].most_common(1)[0][0]
        del g['spellings']
        result.append(g)
    result.sort(key=lambda g: g['name'].lower())
    return result


def brand_groups():
    """Brands that have at least one active product, A to Z, each as
    {slug, name, count, raw}. `raw` lists the exact stored spellings so a brand
    page can filter products with brand__in=raw."""
    rows = (
        Product.objects.filter(is_active=True).exclude(brand='')
        .order_by().values('brand').annotate(n=Count('id'))
    )
    return _group(rows)


def brand_suggestions():
    """Existing brand names (including products currently hidden), one per
    brand, for the admin's Brand field suggestion list."""
    rows = Product.objects.exclude(brand='').order_by().values('brand').annotate(n=Count('id'))
    return [g['name'] for g in _group(rows)]
