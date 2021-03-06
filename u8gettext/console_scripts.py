#!/usr/bin/env python

'''
@date 2015-10-07

A script to convert glyphs of characters in *.po to u8glib supported
font array and prepare for U8Gettext.

It do these things :

1. Extract all characters from inputed po files
2. Find characters' glyphs from inputed font
3. Generate glyphs to u8glib font array to C/C++ sources

@author Hong-She Liang <starofrainnight@gmail.com>
'''

import os
import io
import struct
import six
import bdflib.reader
import argparse
import glob
import polib
import uuid
import os.path

"""
A class just for fix problem that bdflib can't recognize the new style
iterator in python3.
"""
class IteratorFixer(object):
    def __init__(self, iterator):
        self.__iterator = iterator

    def __iter__(self):
        return self.__iterator

    def next(self):
        return six.next(self.__iterator)

def get_font_properties(file_path):
    font_file = open(file_path, "r")

    properties = None
    while(1):
        line = font_file.readline()
        if 'ENDPROPERTIES' in line:
            break

        if 'STARTPROPERTIES' in line:
            properties = dict()
            continue

        if properties is None:
            continue

        line = line.strip()

        line_parties = line.split()
        properties[line_parties[0]] = line_parties[1]

    return properties

def encode_as_c_string(str):
    result = []
    str_bytes = str.encode("utf-8")
    for i in six.moves.range(0, len(str_bytes)):
        ord_c = six.indexbytes(str_bytes, i)

        if (32 <= ord_c) and (ord_c <= 126):
            result.append(chr(ord_c))
        else:
            # Arduino Serial.print() have a strange behavior :
            # If we pass "\x0AFrom this" string to output, it will not
            # correct output with a new line character and string
            # "From this", it will output "\xafrom this". Seems if we
            # have any hex number followed \x0XX, it can't parse correct.
            # So we use octal number instead.
            result.append("\\%03o" % ord_c)

    return ''.join(result)

def generate_languages_source(po_file_paths, utf32_to_u8gchar_mappings):
    result = []

    # Generate character mapping item (from utf32 to u8glib character)
    utf32_keys = [ord(key) for key in six.iterkeys(utf32_to_u8gchar_mappings)]
    utf32_keys.sort()

    result.append("static const U8GettextCharMapping sCharMappings[] U8G_SECTION(\".progmem.U8GettextsCharMappings\") = \n{")
    for key in utf32_keys:
        line = "\t{0x%08X, 0x%02X,}, " % (key, utf32_to_u8gchar_mappings[six.unichr(key)])
        result.append(line)
    result.append("};")
    result.append("static const size_t sCharMappingCount = "
        "ITEM_COUNT_OF_ARRAY(sCharMappings);")

    po_index = 0
    for file_path in po_file_paths:
        language_name = os.path.splitext(os.path.basename(file_path))[0]
        po_file = polib.pofile(file_path)
        translated_entries = po_file.translated_entries()

        # Generate translations for each language

        # We have to generate variables for each text, otherwise the compiler
        # won't compile them into program memory!
        i = 0
        for entry in translated_entries:
            result.append('static const char sMsgId%s_%s[] PROGMEM = "%s";' % (
                po_index, i, encode_as_c_string(entry.msgid)))

            result.append('static const char sMsgStr%s_%s[] PROGMEM = "%s";' % (
                po_index, i, encode_as_c_string(entry.msgstr)))

            i += 1

        result.append('static const U8GettextTranslation sTranslations%s[] U8G_SECTION(".progmem.U8GettextsTranslations") = \n{' % language_name)
        i = 0
        for entry in translated_entries:
            result.append('\t{(const U8GFChar*)&sMsgId%s_%s[0], (const U8GFChar*)&sMsgStr%s_%s[0]},' % (
                po_index, i, po_index, i))
            i += 1

        result.append("};")
        result.append("static const size_t sTranslationsLength%(language)s = "
            "ITEM_COUNT_OF_ARRAY(sTranslations%(language)s);" % {"language":language_name})

        po_index += 1

    # Generate languages
    result.append("static const U8GettextLanguage sLanguages[] = \n{")
    for file_path in po_file_paths:
        language_name = os.path.splitext(os.path.basename(file_path))[0]
        result.append('\t{"%(language)s", '
            'sTranslations%(language)s, '
            '&sTranslationsLength%(language)s}' %
            {"language":language_name})

    result.append("};")
    result.append("static const size_t sLanguagesLength = "
            "ITEM_COUNT_OF_ARRAY(sLanguages);")

    return "\n".join(result)

def gather_characters_from_po_files(po_file_paths):
    characters = set()

    # All visible ASCII charactes must have ..
    for i in six.moves.range(32, 127):
        characters.add(six.unichr(i))

    for afile_path in po_file_paths:
        po_file = polib.pofile(afile_path)
        for anentry in po_file.translated_entries():
            for acharacter in anentry.msgid:
                characters.add(acharacter)

            for acharacter in anentry.msgstr:
                characters.add(acharacter)

        for anentry in po_file.untranslated_entries():
            for acharacter in anentry.msgid:
                characters.add(acharacter)

            for acharacter in anentry.msgstr:
                characters.add(acharacter)

    return characters

def gen_data():
    program_description = 'A script to convert glyphs of characters in *.po to u8glib supported font array'

    parser = argparse.ArgumentParser(description=program_description)
    parser.add_argument(
        '-f',
        '--font',
        required=True,
        help='A bdf font which we will extract glyphs from.')
    parser.add_argument(
        '-p',
        '--po',
        required=True,
        help='Gettext generated PO files pattern')
    parser.add_argument(
        '-o',
        '--output',
        default='U8GettextData.cpp',
        help='Output C/C++ source file path')

    # If the arguments not enough or not fit for the arguments formats, program
    # will exit from here
    args = parser.parse_args()
    po_file_paths = glob.glob(args.po)

    # Analyse all charactes from *.po
    characters = gather_characters_from_po_files(po_file_paths)
    characters = dict.fromkeys(characters, None)

    font_data = []

    # Load font details from bdf file
    unifont_iterator = IteratorFixer(iter(open(args.font, "r").readlines()))
    unifont = bdflib.reader.read_bdf(unifont_iterator)
    unifont_properties = get_font_properties(args.font)

    first_glyph = unifont.glyphs[0]

    uppercase_a_height = 0
    uppercase_a_start = 0
    lowercase_a_start = 0

    # First encoding must not be 0, because u8glib depends on 0 to end
    # the string.
    encoding_start = 1
    encoding_end = encoding_start + len(characters)

    # FIXME We don't have these properties
    font_xascent = 0
    font_xdecent = 0

    if ord('A') in unifont:
        uppercase_a_height = unifont[ord('A')].bbH

    # TODO Give value to upper case and lower case 'A' start position
    header = struct.pack(">BBBbbBHHBBbbbbb",
        0,
        first_glyph.bbW, first_glyph.bbH, first_glyph.bbX, first_glyph.bbY,
        uppercase_a_height, uppercase_a_start, lowercase_a_start,
        encoding_start, encoding_end,
        int(unifont_properties["FONT_DESCENT"]),
        int(unifont_properties["FONT_ASCENT"]),
        int(unifont_properties["FONT_DESCENT"]),
        font_xascent, font_xdecent,
        )
    font_data.append(header)

    u8g_encoding = encoding_start - 1
    utf32_keys = [key for key in six.iterkeys(characters)]
    utf32_keys.sort()

    for acharacter in utf32_keys:
        u8g_encoding += 1
        characters[acharacter] = u8g_encoding

        encoding = ord(acharacter)

        glyph = unifont[encoding]

        glyph_header = struct.pack(">BBBbbb",
            glyph.bbW, glyph.bbH,
            int((glyph.bbW + 7) // 8 * glyph.bbH),
            glyph.bbW,
            glyph.bbX, glyph.bbY,
            )

        glyph_data = []
        for row_pixels in glyph.get_data():
            for i in range(0, len(row_pixels), 2):
                glyph_data.append(chr(int(row_pixels[i:i+2], 16)))

        glyph_data = six.b(''.join(glyph_data))

        font_data.append(glyph_header)
        font_data.append(glyph_data)

    font_data = six.b('').join(font_data)

    # Generate font data C/C++ text data
    font_data_source = []
    for i in range(0, len(font_data)):
        if (i % 16) == 0:
            font_data_source.append("\n  ")

        data_item = "0x%02X" % six.indexbytes(font_data, i)
        data_item = data_item + "," + " " * (5 - len(data_item))
        font_data_source.append(data_item)

    font_data_source = "".join(font_data_source)

    # Generate C/C++ source files
    source_file_name = os.path.basename(args.output)
    source_file_dir = os.path.dirname(args.output)
    source_file_basename, source_file_ext = os.path.splitext(source_file_name)
    header_file_name = "%s.h" % source_file_basename
    header_file_path = os.path.join(source_file_dir, header_file_name)
    font_varaint_name = "sFont"

    source_file = open(args.output, "wb")

    # Generate source file header
    source_file.write(six.b("""
/*
 * Auto generated by u8gettext-gen-data.py
 */

#include <U8Gettext.h>
#include <U8glib.h>

#ifndef ITEM_COUNT_OF_ARRAY
#define ITEM_COUNT_OF_ARRAY(array) (sizeof((array)) / sizeof((array)[0]))
#endif // #ifndef ITEM_COUNT_OF_ARRAY


"""))

    # Generate origin text directly to u8glib font text table
    source_file.write(generate_languages_source(po_file_paths, characters).encode("utf-8"))

    # Generate font data
    source_file.write(six.b("""
static const u8g_fntpgm_uint8_t %(font_varaint_name)s[] U8G_SECTION(".progmem.U8Gettext%(font_varaint_name)s") =
{
%(font_data_source)s
};
static const size_t %(font_varaint_name)sEncodingCount = ITEM_COUNT_OF_ARRAY(%(font_varaint_name)s);
    """ % {"font_varaint_name":font_varaint_name,
        "font_data_source":font_data_source,
        }))

    # Generate U8Gettext context struct variants
    source_file.write(six.b("""
const U8GettextContext __gU8GettextContext
{
\tsLanguages,
\t&sLanguagesLength,
\tsFont,
\t&sFontEncodingCount,
\tsCharMappings,
\t&sCharMappingCount,
};
"""
    ))
    source_file.close()

    # Don't generate header files, they will be included in U8Gettext
    # library.

