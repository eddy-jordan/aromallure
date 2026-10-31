"""
Sorting, filtering and numbered paging shared by the collection, brand pages
and search results.

Prices are compared and sorted by what a customer would actually pay: the sale
price when a valid one is entered (see Product.on_sale), otherwise the normal
price.
"""
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Case, DecimalField, F, When

from .models import Product

PAGE_SIZE = 12
DEFAULT_SORT = 'newest'

# Query-string parameters the catalogue understands. Anything else (for
# example tracking parameters on a social link) is ignored.
CATALOG_PARAMS = {'q', 'page', 'sort', 'type', 'min_price', 'max_price'}

SORT_OPTIONS = [
    ('newest', 'Newest'),
    ('price_asc', 'Price: low to high'),
    ('price_desc', 'Price: high to low'),
    ('name', 'Name: A to Z'),
]
# The trailing id keeps the order stable, so a perfume can't appear on two pages.
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


def _price(raw):
    """A usable non-negative price from the query string, or None."""
    try:
        value = Decimal((raw or '').strip())
    except (InvalidOperation, AttributeError):
        return None
    if not value.is_finite() or value < 0 or value > Decimal('9999999'):
        return None
    return value


def _fmt(value):
    return '' if value is None else format(value, 'f')


def catalog_context(request, queryset, query=''):
    """Apply the sort/filter/page from the request to `queryset` and return the
    template context for the product grid, filter bar and page numbers."""
    get = request.GET

    sort = get.get('sort') if get.get('sort') in _ORDERING else DEFAULT_SORT
    ptype = get.get('type') if get.get('type') in dict(TYPE_OPTIONS) else ''
    low, high = _price(get.get('min_price')), _price(get.get('max_price'))
    if low is not None and high is not None and low > high:
        low, high = high, low

    queryset = queryset.annotate(effective_price=_EFFECTIVE_PRICE)
    if ptype:
        queryset = queryset.filter(concentration=ptype)
    if low is not None:
        queryset = queryset.filter(effective_price__gte=low)
    if high is not None:
        queryset = queryset.filter(effective_price__lte=high)
    queryset = queryset.order_by(*_ORDERING[sort])

    paginator = Paginator(queryset, PAGE_SIZE)
    products = paginator.get_page(get.get('page', 1))

    page_range = []
    if paginator.num_pages > 1:
        for n in paginator.get_elided_page_range(products.number, on_each_side=1, on_ends=1):
            page_range.append({'num': n, 'current': n == products.number} if isinstance(n, int) else {'gap': True})

    # Only meaningful values go into links, so pager links carry the current
    # view with no junk. The Clear link keeps just the search term.
    params = []
    if query:
        params.append(('q', query))
    if sort != DEFAULT_SORT:
        params.append(('sort', sort))
    if ptype:
        params.append(('type', ptype))
    if low is not None:
        params.append(('min_price', _fmt(low)))
    if high is not None:
        params.append(('max_price', _fmt(high)))
    qs_prefix = urlencode(params) + '&' if params else ''
    clear = urlencode([('q', query)]) if query else ''

    filtering = bool(ptype or low is not None or high is not None)
    return {
        'products': products,
        'page_range': page_range,
        'qs_prefix': qs_prefix,
        'sort_options': SORT_OPTIONS,
        'type_options': TYPE_OPTIONS,
        'f': {'sort': sort, 'type': ptype, 'min_price': _fmt(low), 'max_price': _fmt(high)},
        'filtering': filtering,
        'custom_view': filtering or sort != DEFAULT_SORT,
        'clear_url': request.path + ('?' + clear if clear else '') + '#collection',
    }
