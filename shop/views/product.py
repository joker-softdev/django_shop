# -*- coding: utf-8 -*-
import os
import itertools
from django.shortcuts import get_object_or_404
from django.template import RequestContext
from django.template.loader import select_template
from rest_framework import serializers
from rest_framework import generics
from rest_framework.renderers import TemplateHTMLRenderer, BrowsableAPIRenderer
from shop.money.rest import JSONRenderer
from shop.models.product import BaseProduct


class ProductSerializerBase(serializers.ModelSerializer):
    """
    Common serializer for the Product model, both for the ProductSummarySerializer and the
    ProductDetailSerializer.
    """
    price = serializers.SerializerMethodField()
    availability = serializers.SerializerMethodField()

    class Meta:
        model = getattr(BaseProduct, 'MaterializedModel')
        fields = ('name', 'identifier', 'price', 'availability')

    def get_price(self, product):
        return product.get_price(self.context['request'])

    def get_availability(self, product):
        return product.get_availability(self.context['request'])


class ProductSummarySerializer(ProductSerializerBase):
    """
    Serialize a subset of the Product model, suitable for list views, cart- and order-lists.
    """
    product_url = serializers.CharField(source='get_absolute_url', read_only=True)
    html = serializers.SerializerMethodField()

    class Meta(ProductSerializerBase.Meta):
        fields = ProductSerializerBase.Meta.fields + ('product_url', 'html') \
            + getattr(ProductSerializerBase.Meta.model, 'summary_fields', ())

    def find_template(self, product):
        app_label = product._meta.app_label.lower()
        basename = '{}-summary.html'.format(product.__class__.__name__.lower())
        prefix = self.context.get('serializer_name')
        templates = [(app_label, basename), (app_label, 'product-summary.html'), ('shop', 'product-summary.html')]
        if prefix:
            prefixed_templates = [(base, prefix + '-' + leaf) for base, leaf in templates]
            templates = itertools.chain.from_iterable(zip(prefixed_templates, templates))
        templates = [os.path.join(base, leaf) for base, leaf in templates]
        return select_template(templates)

    def get_html(self, product):
        """
        Return a HTML snippet containing a rendered summary for this product.
        """
        template = self.find_template(product)
        request = self.context['request']
        context = RequestContext(request, {'product': product})
        return template.render(context)


class ProductDetailSerializer(ProductSerializerBase):
    """
    Serialize all fields of the Product model, for the products detail view.
    """
    infix = 'detail'

    class Meta(ProductSerializerBase.Meta):
        fields = ProductSerializerBase.Meta.fields \
            + getattr(ProductSerializerBase.Meta.model, 'detail_fields', ())


class ProductRetrieveView(generics.RetrieveAPIView):
    """
    View responsible for rendering the products details.
    Additionally an extra method as shown in products lists, cart lists
    and order item lists.
    """
    serializer_class = ProductDetailSerializer
    renderer_classes = (TemplateHTMLRenderer, JSONRenderer, BrowsableAPIRenderer)

    def get_object(self):
        assert self.lookup_url_kwarg in self.kwargs
        filter_kwargs = {self.lookup_field: self.kwargs[self.lookup_url_kwarg]}
        queryset = getattr(BaseProduct, 'MaterializedModel').objects
        queryset = queryset.filter(self.limit_choices_to, **filter_kwargs)
        product = get_object_or_404(queryset)
        self.product = product
        return product

    def get_template_names(self):
        app_label = self.product._meta.app_label.lower()
        basename = '{}-detail.html'.format(self.product.__class__.__name__.lower())
        return [
            os.path.join(app_label, basename),
            os.path.join(app_label, 'product-detail.html'),
            'shop/product-detail.html',
        ]

    def get_renderer_context(self):
        context = super(ProductRetrieveView, self).get_renderer_context()
        # if the used renderer is a `TemplateHTMLRenderer`, then enrich the
        # context with some unserializable Python objects
        if context['request'].accepted_renderer.format == 'html':
            context['request'].passo = 'passo'  # TODO: add what we need here
        return context

    def get(self, request, *args, **kwargs):
        self.limit_choices_to = kwargs.pop('limit_choices_to')
        self.lookup_url_kwarg = kwargs.pop('lookup_url_kwarg')
        self.lookup_field = kwargs.pop('lookup_field')
        return self.retrieve(request, *args, **kwargs)


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSummarySerializer
    renderer_classes = (TemplateHTMLRenderer, JSONRenderer, BrowsableAPIRenderer)

    def get_queryset(self):
        qs = getattr(BaseProduct, 'MaterializedModel').objects.filter(self.limit_choices_to)

        # restrict products for current CMS page
        current_page = self.request._request.current_page
        if current_page.publisher_is_draft:
            current_page = current_page.publisher_public
        qs = qs.filter(cms_pages=current_page)
        return qs

    def paginate_queryset(self, queryset):
        page = super(ProductListView, self).paginate_queryset(queryset)
        self.paginator = page.paginator
        return page

    def get_renderer_context(self):
        context = super(ProductListView, self).get_renderer_context()
        # The RESTframework does not add the paginator to the rendering context
        context['request'].paginator = self.paginator
        return context

    def get(self, request, *args, **kwargs):
        self.limit_choices_to = kwargs.pop('limit_choices_to')
        self.template_name = kwargs.pop('template_name', 'shop/products-list.html')
        return self.list(request, *args, **kwargs)
