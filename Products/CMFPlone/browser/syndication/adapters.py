from uuid import uuid3
from uuid import NAMESPACE_OID

from lxml.html import fromstring, tostring

from zope.component.hooks import getSite
from zope.component import adapts
from zope.interface import implements
from zope.interface import Interface
from zope.component import queryMultiAdapter

from DateTime import DateTime
from OFS.interfaces import IItem

from Products.CMFCore.utils import getToolByName

from Products.CMFPlone.interfaces.syndication import IFeed
from Products.CMFPlone.interfaces.syndication import IFeedItem
from Products.CMFPlone.interfaces.syndication import ISearchFeed
from Products.CMFPlone.interfaces.syndication import IFeedSettings
from Products.ATContentTypes.interfaces.file import IFileContent
from plone.uuid.interfaces import IUUID
from zope.cachedescriptors.property import Lazy as lazy_property

# this might be a little silly but it's possible to not use
# Products.CMFPlone with dexterity content types
try:
    from plone.dexterity.interfaces import IDexterityContent
except ImportError:
    class IDexterityContent(Interface):
        pass
try:
    from plone.rfc822.interfaces import IPrimaryFieldInfo
except ImportError:
    class IPrimaryFieldInfo(Interface):
        pass
try:
    from plone.namedfile.interfaces import INamedField
except ImportError:
    class INamedField(Interface):
        pass


class BaseFeedData(object):

    def __init__(self, context):
        self.context = context
        self.settings = IFeedSettings(context)
        self.site = getSite()
        if self.show_about:
            self.pm = getToolByName(self.context, 'portal_membership')
        pprops = getToolByName(self.context, 'portal_properties')
        self.site_props = pprops.site_properties
        self.view_action_types = self.site_props.getProperty(
            'typesUseViewActionInListings', ('File', 'Image'))

    @lazy_property
    def show_about(self):
        return self.settings.show_author_info

    @lazy_property
    def current_date(self):
        return DateTime()

    @property
    def link(self):
        return self.base_url

    @lazy_property
    def base_url(self):
        return self.context.absolute_url()

    @property
    def title(self):
        return self.context.Title()

    @property
    def description(self):
        return self.context.Description()

    @property
    def categories(self):
        return self.context.Subject()

    @property
    def published(self):
        date = self.context.EffectiveDate()
        if date and date != 'None':
            return DateTime(date)

    @property
    def modified(self):
        date = self.context.ModificationDate()
        if date:
            return DateTime(date)

    @property
    def uid(self):
        uuid = IUUID(self.context, None)
        if uuid is None and hasattr(self.context, 'UID'):
            return self.context.UID()
        return uuid

    @property
    def rights(self):
        return self.context.Rights()

    @property
    def publisher(self):
        if hasattr(self.context, 'Publisher'):
            return self.context.Publisher()
        return 'No Publisher'


class FolderFeed(BaseFeedData):
    implements(IFeed)

    @lazy_property
    def author(self):
        if self.show_about:
            creator = self.context.Creator()
            member = self.pm.getMemberById(creator)
            return member

    @property
    def author_name(self):
        if self.author:
            return self.author.getProperty('fullname')

    @property
    def author_email(self):
        if self.author:
            return self.author.getProperty('email')

    @property
    def logo(self):
        return '%s/logo.png' % self.site.absolute_url()

    @property
    def icon(self):
        return '%s/favicon.ico' % self.site.absolute_url()

    def _brains(self):
        catalog = getToolByName(self.context, 'portal_catalog')
        return catalog(path={
            'query': '/'.join(self.context.getPhysicalPath()),
            'depth': 1
            })

    def _items(self):
        """
        do catalog query
        """
        return [b.getObject() for b in self._brains()]

    @property
    def items(self):
        for item in self._items():
            # look for custom adapter
            # otherwise, just use default
            adapter = queryMultiAdapter((item, self), IFeedItem)
            if adapter is None:
                adapter = BaseItem(item, self)
            yield adapter

    @property
    def limit(self):
        return self.settings.max_items

    @property
    def language(self):
        langtool = getToolByName(self.context, 'portal_languages')
        return langtool.getDefaultLanguage()


class CollectionFeed(FolderFeed):
    def _brains(self):
        return self.context.queryCatalog(batch=False)[:self.limit]


class SearchFeed(FolderFeed):
    implements(ISearchFeed)

    def _brains(self):
        max_items = self.limit
        request = self.context.REQUEST
        start = int(request.get('b_start', 0))
        end = int(request.get('b_end', start + max_items))
        request.set('sort_order', 'reverse')
        request.set('sort_on', request.get('sort_on', 'effective'))
        return self.context.queryCatalog(show_all=1, use_types_blacklist=True,
            use_navigation_root=True)[start:end]


class BaseItem(BaseFeedData):
    implements(IFeedItem)
    adapts(IItem, IFeed)

    def __init__(self, context, feed):
        self.context = context
        self.feed = feed

    @property
    def created(self):
        return self.context.created()

    @lazy_property
    def author(self):
        if self.feed.show_about:
            creator = self.context.Creator()
            member = self.feed.pm.getMemberById(creator)
            return member and member.getProperty('fullname') or creator

    @property
    def author_name(self):
        author = self.author
        if author and hasattr(author, 'getProperty'):
            return author.getProperty('fullname')

    @property
    def author_email(self):
        author = self.author
        if author and hasattr(author, 'getProperty'):
            return author.getProperty('email')

    @property
    def body(self):
        if hasattr(self.context, 'getText'):
            return self.context.getText()
        elif hasattr(self.context, 'text'):
            return self.context.text
        return self.description

    @property
    def friendly_body(self):
        body = self.body
        if not body:
            return body

        dom = fromstring(body)
        # first, remove all attributes except for href
        for el in dom.cssselect('*'):
            for attr in el.attrib.keys():
                if attr != 'href':
                    del el.attrib[attr]

        for h2 in dom.cssselect('h2'):
            h2.tag = 'p'
        # XXX No way with lxml to unwrap!?
        # for span in dom.cssselect('span'):
        #     span.unwrap()
        for ol in dom.cssselect('ol'):
            ol.tag = 'ul'
        result = tostring(dom)
        # Remove some whitespace
        result = result.replace('\n', '')
        result.strip()
        return result

    @property
    def link(self):
        url = self.base_url
        if self.context.portal_type in self.feed.view_action_types:
            url = url + '/view'
        return url

    guid = link

    @property
    def has_enclosure(self):
        return IFileContent.providedBy(self.context)

    @lazy_property
    def file(self):
        if self.has_enclosure:
            return self.context.getFile()

    @property
    def file_url(self):
        url = self.base_url
        fi = self.file
        if fi is not None:
            filename = fi.getFilename()
            if filename:
                url += '/@@download/file/%s' + filename
        return url

    @property
    def file_length(self):
        return self.file.get_size()

    @property
    def file_type(self):
        return self.file.getContentType()

    @property
    def image_url(self):
        # Support up to 768px max size
        url = "%s/image_large" % self.base_url
        return url

    @property
    def image_mime_type(self):
        if self.has_image:
            img = self.context.getImage()
            return img.content_type

    @property
    def image_caption(self):
        result = ''
        if self.has_image:
            caption = getattr(self.context, 'imageCaption', None)
            if caption and caption != '':
                result = caption
            else:
                result = self.description
        return result

    @property
    def has_image(self):
        result = False
        img = getattr(self.context, 'getImage', None)
        if img:
            img_contents = img()
            result = img_contents and img_contents != ''
        return result

    def duid(self, value):
        uid = uuid3(NAMESPACE_OID, self.uid + str(value))
        return uid.hex


class DexterityItem(BaseItem):
    adapts(IDexterityContent, IFeed)

    has_image = False

    def __init__(self, context, feed):
        super(DexterityItem, self).__init__(context, feed)
        self.dexterity = IDexterityContent.providedBy(context)
        self.primary = IPrimaryFieldInfo(self.context, None)

    @property
    def file_url(self):
        url = self.base_url
        fi = self.file
        if fi is not None:
            filename = fi.filename
            if filename:
                url += '/@@download/%s/%s' % (
                    self.primary.field.__name__, filename)
        return url

    @property
    def has_enclosure(self):
        if self.primary:
            return INamedField.providedBy(self.primary.field)
        else:
            return False

    @lazy_property
    def file(self):
        if self.has_enclosure:
            return self.primary.field.get(self.context)

    @property
    def file_length(self):
        return self.file.getSize()

    @property
    def file_type(self):
        return self.file.contentType

    @property
    def image_url(self):
        return None

    image_caption = image_mime_type = image_url