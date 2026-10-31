"""
Sorting, the type filter and "Show more" paging shared by the collection,
brand pages and search results.

Paging works by growing the list instead of flipping pages: `page=N` means
"the first N pages' worth of perfumes", so a customer who has pressed Show more
three times and then refreshes (or comes back with the browser's Back button)
still sees everything they had loaded.

Sorting by price uses what a customer would actually pay: the sale price when a
valid one is entered (see Product.on_sale), otherwise the normal price.
"""
from urllib.parse import urlencode

from django.db.models import Case, DecimalField, F, When

from .models import Product

PAGE_SIZE = 12
DEFAULT_SORT = 'newest'

# Query-string parameters the catalogue understands. Anything else (for
# example tracking parameters on a social link) is ignored.
CATALOG_PARAMS = {'q', 'page', 'sort', 'type'}

SORT_OPTIONS = [
    ('newest', 'Newest'),
    ('price_asc', 'Price: low to high'),
    ('price_desc', 'Price: high to low'),
    ('name', 'Name: A to Z'),
]
# The trailing id keeps the order stable, so a perfume can't repeat or vanish
# when more are loaded.
_ORDERING = {
    'newest':     ['-created_at', '-id'],
    'price_asc':  ['effective_price', 'name', 'id'],
    'price_desc': ['-effective_price', 'name', 'id'],
    'name':       ['name', 'id'],
}
TYPE_OPTIONS = Product.CONCENTRATION_CHOICES

_EFFECTIVE_PRICE = Case(
    When(sale_price__gt=0, sale_price__lt=F('price'), then=F('sale_price')),
    default=F('price'),
    output_field=DecimalField(max_digits=8, decimal_places=2),
)


def catalog_context(request, queryset, query=''):
    """Apply the sort, type filter and "how many pages so far" from the request
    to `queryset` and return the template context."""
    get = request.GET

    sort = get.get('sort') if get.get('sort') in _ORDERING else DEFAULT_SORT
    ptype = get.get('type') if get.get('type') in dict(TYPE_OPTIONS) else ''

    queryset = queryset.annotate(effective_price=_EFFECTIVE_PRICE)
    if ptype:
        queryset = queryset.filter(concentration=ptype)
    queryset = queryset.order_by(*_ORDERING[sort])

    total = queryset.count()
    last_page = max(1, -(-total // PAGE_SIZE))
    try:
        pages = int(get.get('page', 1))
    except (TypeError, ValueError):
        pages = 1
    pages = min(max(pages, 1), last_page)
    products = list(queryset[:pages * PAGE_SIZE])

    # Only meaningful values go into links, so they carry the current view with
    # no junk. The Clear link keeps just the search term.
    params = []
    if query:
        params.append(('q', query))
    if sort != DEFAULT_SORT:
        params.append(('sort', sort))
    if ptype:
        params.append(('type', ptype))
    qs_prefix = urlencode(params) + '&' if params else ''
    clear = urlencode([('q', query)]) if query else ''

    filtering = bool(ptype)
    return {
        'products': products,
        'total': total,
        'shown_count': len(products),
        'has_more': len(products) < total,
        'next_page': pages + 1,
        'progress': int(len(products) * 100 / total) if total else 100,
        # Showing a counter and button only makes sense once there is more than
        # one page's worth.
        'show_more_area': total > PAGE_SIZE,
        'qs_prefix': qs_prefix,
        'sort_options': SORT_OPTIONS,
        'type_options': TYPE_OPTIONS,
        'f': {'sort': sort, 'type': ptype},
        'filtering': filtering,
        'custom_view': filtering or sort != DEFAULT_SORT,
        'clear_url': request.path + ('?' + clear if clear else '') + '#collection',
    }
