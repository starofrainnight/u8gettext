#!/usr/bin/env python

'''
@date 2015-10-07

A script to convert glyphs of characters in *.po to u8glib supported 
font array (C/C++).

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

def gather_characters_from_po_files(po_file_paths):
    characters = set()
    
    # All visible ASCII charactes must have ..
    for i in range(32, 127):
        characters.add(chr(i))
        
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
    
def main():
    program_description = 'A script to convert glyphs of characters in *.po to u8glib supported font array'
    
    parser = argparse.ArgumentParser(description=program_description)
    parser.add_argument(
        '-f',
        '--font',
        help='A bdf font which we will extract glyphs from.')
    parser.add_argument(
        '-p',
        '--po', 
        help='Gettext generated PO files pattern')
    parser.add_argument(
        '-o',
        '--output',
        help='Output C/C++ source file path')
    
    # If the arguments not enough or not fit for the arguments formats, program
    # will exit from here
    args = parser.parse_args()
    
    # Analyse all charactes from *.po
    characters = gather_characters_from_po_files(glob.glob(args.po))
    characters = dict.fromkeys(characters, None)
    
    font_data = []

    # Load font details from bdf file
    unifont_iterator = IteratorFixer(iter(open(args.font, "r").readlines()))
    unifont = bdflib.reader.read_bdf(unifont_iterator)
    unifont_properties = get_font_properties(args.font)
    
    print("Font properties : %s" % unifont_properties)
    
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
    
    for acharacter in six.iterkeys(characters):
        encoding = ord(acharacter)
    
        glyph = unifont[encoding]
        
        glyph_header = struct.pack(">BBBbbb", 
            glyph.bbW, glyph.bbH,
            int((int(glyph.bbW) + 7)/8 * int(glyph.bbH)),
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
    
if __name__ == "__main__":
    main()