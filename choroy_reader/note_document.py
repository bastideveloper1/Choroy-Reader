"""Rich note documents: embedded images, text flow and editable image positions."""
import base64
import html

from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QTextCursor, QTextDocument, QTextFrameFormat, QTextImageFormat


POSITIONS = {'left': QTextFrameFormat.FloatLeft, 'right': QTextFrameFormat.FloatRight,
             'inline': QTextFrameFormat.InFlow}


def document_of(wrapper):
    return wrapper.textDocument() if hasattr(wrapper, 'textDocument') else wrapper


def note_html(note):
    if note.get('html'):
        return note['html']
    # Migrate old plain notes without interpreting their text as HTML.
    body = html.escape(note.get('text', '')).replace('\n', '<br>')
    images = ''
    for source in note.get('images', []):
        if not source.startswith('data:image/'):
            continue
        image = QImage.fromData(base64.b64decode(source.split(',', 1)[1]))
        height = 180 * image.height() / max(1, image.width())
        images += f'<p><img src="{html.escape(source, quote=True)}" width="180" height="{height}"></p>'
    return '<p>' + body + '</p>' + images


def image_cursor(document, position):
    if position < 0 or position >= document.characterCount() - 1:
        return None
    cursor = QTextCursor(document)
    cursor.setPosition(position)
    cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
    return cursor if cursor.charFormat().isImageFormat() else None


def insert_image(document, position, source, alignment='left', width=None):
    """Insert one editable image character; Qt keeps the anchor as text changes."""
    image = QImage.fromData(base64.b64decode(source.split(',', 1)[1]))
    if image.isNull():
        return -1
    document.addResource(QTextDocument.ImageResource, QUrl(source), image)
    available = max(120, document.textWidth() - 16)
    width = min(width or min(180, available * 0.45), available)
    fmt = QTextImageFormat()
    fmt.setName(source)
    fmt.setWidth(width)
    fmt.setHeight(width * image.height() / max(1, image.width()))
    cursor = QTextCursor(document)
    cursor.setPosition(max(0, min(position, document.characterCount() - 1)))
    cursor.insertImage(fmt, POSITIONS.get(alignment, QTextFrameFormat.FloatLeft))
    return cursor.position() - 1


def image_layout(document):
    # Keep wide images usable when returning from the expanded editor.
    available = max(80, document.textWidth() - 12)
    block = document.begin()
    oversized = []
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.charFormat().isImageFormat():
                fmt = fragment.charFormat().toImageFormat()
                if fmt.width() > available:
                    fmt.setHeight(fmt.height() * available / fmt.width())
                    fmt.setWidth(available)
                    oversized.append((fragment.position(), fragment.length(), fmt))
            iterator += 1
        block = block.next()
    for position, length, fmt in oversized:
        cursor = QTextCursor(document)
        cursor.setPosition(position)
        cursor.setPosition(position + length, QTextCursor.KeepAnchor)
        cursor.setCharFormat(fmt)
    layout = document.documentLayout()
    layout.documentSize()
    floats = {}

    def visit(frame):
        for child in frame.childFrames():
            if child.firstPosition() > child.lastPosition():
                floats[child.lastPosition()] = child
            visit(child)
    visit(document.rootFrame())
    result = []
    block = document.begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.charFormat().isImageFormat():
                fmt = fragment.charFormat().toImageFormat()
                # Identical adjacent images can share a single text fragment.
                for position in range(fragment.position(), fragment.position() + fragment.length()):
                    frame = floats.get(position)
                    if frame:
                        rect = layout.frameBoundingRect(frame)
                        x, y = rect.x(), rect.y()
                        align = 'right' if frame.frameFormat().position() == QTextFrameFormat.FloatRight else 'left'
                    else:
                        rect = layout.blockBoundingRect(block)
                        offset = position - block.position()
                        line = block.layout().lineForTextPosition(offset)
                        if not line.isValid():
                            continue
                        x = rect.x() + line.cursorToX(offset)[0]
                        y = rect.y() + line.y() + max(0, line.ascent() - fmt.height())
                        align = 'inline'
                    result.append(dict(position=position, x=x, y=y, width=fmt.width(),
                                       height=fmt.height(), alignment=align))
            iterator += 1
        block = block.next()
    return result


def change_image(document, position, target, alignment, width=0):
    cursor = image_cursor(document, position)
    if cursor is None:
        return -1
    fmt = cursor.charFormat().toImageFormat()
    if width > 0:
        ratio = fmt.height() / max(1, fmt.width())
        fmt.setWidth(width)
        fmt.setHeight(width * ratio)
    target = max(0, min(target, document.characterCount() - 1))
    cursor.beginEditBlock()
    cursor.removeSelectedText()
    if target > position:
        target -= 1
    cursor.setPosition(target)
    cursor.insertImage(fmt, POSITIONS.get(alignment, QTextFrameFormat.InFlow))
    cursor.endEditBlock()
    return cursor.position() - 1


def remove_image(document, position):
    cursor = image_cursor(document, position)
    if cursor is None:
        return False
    cursor.removeSelectedText()
    return True
