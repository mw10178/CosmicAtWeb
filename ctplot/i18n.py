import gettext
import os

text_domain = 'ctplot'
locale_dir = os.path.dirname(__file__) + '/locale'

t = gettext.translation(text_domain, locale_dir,
    languages=['de'], fallback=True)

_ = t.gettext
