import csv
import os
import re


def _generate_static_files(out_path, in_path, index_html='index.html'):
    # 1. generating dictionary from csv
    dictionary = {}

    with open('ctplot/dict.csv') as f:
        d = csv.DictReader(f, fieldnames=('en', 'de', 'key'))
        next(d)  # skipping first row which is supposed to be the label

        for row in d:
            dictionary[
                row['key'] if row['key'] else row['en'].lower()  # using english version as key fallback
            ] = row['en'], row['de']

    # 2. open & read index.html
    with open(os.path.join(in_path, index_html)) as f:
        in_str = f.read()

    # 3. remove comments around double curly braces
    in_str.replace('/*{{', '{{')
    in_str.replace('}}*/', '}}')

    # 4. insert files (css & js)
    for match in re.finditer(r"(/\*)?\{\{INSERT (?P<filename>[a-zA-Z0-9 \-_./]+)\}\}(\*/)?", in_str):
        with open(os.path.join(in_path, match.group("filename"))) as f:
            in_str = in_str.replace(match.group(), "/* inserted file: %s */\n%s" % (match.group("filename"), f.read()))

    # 5. translate
    out_de = out_en = in_str

    for match in re.finditer(r"(\/\*)?\{\{(?P<key>[a-zA-Z0-9 \-_]+)( % (?P<insert>.*))?\}\}(\*\/)?", in_str):
        insert = match.group("insert")
        strings_en = ()
        strings_de = ()

        if insert:
            for w in insert.split(","):
                strings_en += (dictionary[w][0] if w in dictionary else w,)
                strings_de += (dictionary[w][1] if w in dictionary else w,)

        try:
            key = str.lower(match.group('key'))
            if (strings_en.count == 2):
                out_en = out_en.replace(match.group(), strings_en[0]+dictionary[key][0]+strings_en[1])
                out_de = out_de.replace(match.group(), strings_en[0]+dictionary[key][1]+strings_en[1])
            else:
                out_en = out_en.replace(match.group(), dictionary[key][0])
                out_de = out_de.replace(match.group(), dictionary[key][1])
        except KeyError:
            print "The key '%s' could not be found in the dictionary" % match.group('key')
        except TypeError:
            print "The values could not be inserted in the key '%s'" % match.group('key')

    # 6. output static file
    with open(os.path.join(out_path, 'en', index_html), 'w') as f:
        f.write(out_en)

    with open(os.path.join(out_path, 'de', index_html), 'w') as f:
        f.write(out_de)


def generate_static_files(target_dir):
    _generate_static_files(target_dir, 'ctplot/static')


generate_static_files('ctplot/static')