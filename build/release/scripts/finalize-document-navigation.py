#!/usr/bin/env python3
"""Create native Word TOC, cover, section headers and page-number fields via UNO."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

import uno
from com.sun.star.beans import PropertyValue
from com.sun.star.style import TabStop


def prop(name, value):
    p = PropertyValue(); p.Name = name; p.Value = value
    return p


def paragraphs(doc):
    enum = doc.Text.createEnumeration()
    while enum.hasMoreElements():
        p = enum.nextElement()
        if p.supportsService('com.sun.star.text.Paragraph'):
            yield p


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('document', type=Path)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--refresh-only', action='store_true')
    args = parser.parse_args()
    pipe = 'pixiu_doc_' + uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix='pixiu-navigation-') as profile:
        process = subprocess.Popen(['libreoffice', '--headless', '--nologo', '--nodefault', '--norestore',
            '-env:UserInstallation=' + Path(profile).as_uri(),
            '--accept=pipe,name=' + pipe + ';urp;StarOffice.ComponentContext'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        doc = None
        try:
            local = uno.getComponentContext()
            resolver = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)
            for _ in range(100):
                try:
                    context = resolver.resolve('uno:pipe,name=' + pipe + ';urp;StarOffice.ComponentContext')
                    break
                except Exception:
                    time.sleep(0.1)
            else:
                raise RuntimeError('LibreOffice UNO did not start')
            desktop = context.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', context)
            doc = desktop.loadComponentFromURL(args.document.resolve().as_uri(), '_blank', 0,
                (prop('Hidden', True), prop('UpdateDocMode', 3)))
            if args.refresh_only:
                indexes = doc.getDocumentIndexes()
                for _ in range(2):
                    for i in range(indexes.Count): indexes.getByIndex(i).update()
                    doc.TextFields.refresh(); doc.refresh()
                doc.DocumentProperties.Author = ''; doc.DocumentProperties.ModifiedBy = ''
                doc.storeAsURL(args.document.resolve().as_uri(), (prop('FilterName', 'Office Open XML Text'), prop('Overwrite', True)))
                doc.storeToURL(args.pdf.resolve().as_uri(), (prop('FilterName', 'writer_pdf_Export'), prop('Overwrite', True)))
                print('Existing DOCX contents and fields updated')
                return
            styles = doc.StyleFamilies.getByName('PageStyles')
            page_before = uno.Enum('com.sun.star.style.BreakType', 'PAGE_BEFORE')
            right = uno.Enum('com.sun.star.style.TabAlign', 'RIGHT')
            center = uno.Enum('com.sun.star.style.ParagraphAdjust', 'CENTER')

            def page_style(name, header, footer):
                style = doc.createInstance('com.sun.star.style.PageStyle')
                styles.insertByName(name, style)
                style.Width = 21000; style.Height = 29700
                style.LeftMargin = 2000; style.RightMargin = 2000
                style.TopMargin = 1800; style.BottomMargin = 1800
                style.HeaderIsOn = header; style.FooterIsOn = footer
                style.HeaderIsShared = True; style.FooterIsShared = True
                style.FirstIsShared = True
                style.FollowStyle = name
                if header:
                    style.HeaderBodyDistance = 500
                    ht = style.HeaderText
                    cur = ht.createTextCursor()
                    cur.CharFontName = 'Noto Sans CJK SC'; cur.CharFontNameAsian = 'Noto Sans CJK SC'
                    cur.CharHeight = 9; cur.CharHeightAsian = 9
                    tab = TabStop(); tab.Position = 17000; tab.Alignment = right; tab.FillChar = ' '
                    cur.ParaTabStops = (tab,)
                    ht.insertString(cur, 'PIXIU 技术方案\t', False)
                    if name == 'PIXIU Contents':
                        ht.insertString(cur, '目录', False)
                    else:
                        field = doc.createInstance('com.sun.star.text.textfield.Chapter')
                        field.Level = 0
                        field.ChapterFormat = uno.getConstantByName('com.sun.star.text.ChapterFormat.NAME')
                        ht.insertTextContent(cur, field, False)
                if footer:
                    style.FooterBodyDistance = 500
                    ft = style.FooterText; cur = ft.createTextCursor()
                    cur.ParaAdjust = center; cur.CharHeight = 9
                    cur.CharFontName = "Noto Sans CJK SC"; cur.CharFontNameAsian = "Noto Sans CJK SC"
                    cur.CharHeightAsian = 9; cur.CharColor = 0x111111
                    field = doc.createInstance('com.sun.star.text.textfield.PageNumber')
                    field.NumberingType = uno.getConstantByName('com.sun.star.style.NumberingType.PAGE_DESCRIPTOR')
                    field.SubType = uno.Enum('com.sun.star.text.PageNumberType', 'CURRENT')
                    field.Offset = 0
                    ft.insertTextContent(cur, field, False)
                return style

            cover = page_style('PIXIU Cover', False, False)
            contents = page_style('PIXIU Contents', True, True)
            contents.NumberingType = uno.getConstantByName('com.sun.star.style.NumberingType.ROMAN_UPPER')
            body_style = page_style('PIXIU Body', True, True)
            body_style.NumberingType = uno.getConstantByName('com.sun.star.style.NumberingType.ARABIC')
            cover.FollowStyle = 'PIXIU Contents'
            first_chapter = None
            cover_paragraphs = []
            chapter_count = 0
            for p in list(paragraphs(doc)):
                style = p.ParaStyleName
                if style.startswith('Heading '):
                    try: level = int(style.split()[-1])
                    except ValueError: continue
                    if level >= 2:
                        p.ParaStyleName = 'Heading ' + str(level - 1)
                        p.OutlineLevel = level - 1
                        if level == 2:
                            chapter_count += 1
                            p.BreakType = page_before
                            if first_chapter is None: first_chapter = p
                if first_chapter is None:
                    cover_paragraphs.append(p)
            if first_chapter is None or chapter_count != 8:
                raise RuntimeError('Expected eight major document chapters')
            for i, p in enumerate(cover_paragraphs):
                p.ParaStyleName = 'Title' if i == 0 else 'Subtitle'
                p.ParaAdjust = center
                p.ParaTopMargin = 650 if i else 3600
                p.ParaBottomMargin = 400
                p.CharFontName = 'Noto Sans CJK SC'; p.CharFontNameAsian = 'Noto Sans CJK SC'
                p.CharHeight = 30 if i == 0 else (16 if i == 1 else 12)
                p.CharHeightAsian = p.CharHeight
                p.CharColor = 0x111111
                p.OutlineLevel = 0
            cover_paragraphs[0].PageDescName = 'PIXIU Cover'
            first_title = first_chapter.String
            cursor = doc.Text.createTextCursorByRange(first_chapter.Start)
            doc.Text.insertControlCharacter(cursor, uno.getConstantByName('com.sun.star.text.ControlCharacter.PARAGRAPH_BREAK'), False)
            # UNO paragraph ranges can move when a paragraph break is inserted.
            # Re-find the real heading and the newly inserted empty paragraph.
            ps = list(paragraphs(doc))
            position = next(i for i, p in enumerate(ps) if p.String == first_title)
            first_chapter = ps[position]
            anchor = ps[position - 1]
            if anchor.String:
                raise RuntimeError('TOC anchor must be an empty paragraph')
            first_chapter.PageDescName = 'PIXIU Body'
            first_chapter.PageNumberOffset = 1
            first_chapter.BreakType = page_before
            anchor.PageDescName = 'PIXIU Contents'
            anchor.BreakType = page_before
            anchor.PageNumberOffset = 1
            anchor.ParaStyleName = 'Standard'
            anchor.OutlineLevel = 0
            paragraph_styles = doc.StyleFamilies.getByName('ParagraphStyles')
            for level in range(1, 4):
                paragraph_styles.getByName('Heading ' + str(level)).OutlineLevel = level
            cursor = doc.Text.createTextCursorByRange(anchor.Start)
            index = doc.createInstance('com.sun.star.text.ContentIndex')
            index.CreateFromOutline = True
            index.CreateFromMarks = False
            index.Level = 2
            index.Title = '目录'
            doc.Text.insertTextContent(cursor, index, False)
            # Creating an index changes pagination; refresh twice before export.
            for _ in range(2):
                index.update(); doc.TextFields.refresh(); doc.refresh()
            doc.DocumentProperties.Author = ''
            doc.DocumentProperties.ModifiedBy = ''
            doc.storeAsURL(args.document.resolve().as_uri(), (prop('FilterName', 'Office Open XML Text'), prop('Overwrite', True)))
            doc.storeToURL(args.pdf.resolve().as_uri(), (prop('FilterName', 'writer_pdf_Export'), prop('Overwrite', True)))
            print('Native TOC, cover, chapter headers and centered page-number fields created')
        finally:
            if doc is not None: doc.close(True)
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait()


if __name__ == '__main__':
    main()
