import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Dialog {
    id: editor
    objectName: "noteEditor"
    required property var hostWindow
    required property var markerColors
    property string readerIdentity: ""
    property string ownerIdentity: ""
    property string note_id: ""
    property string paper_color: "#ffe88f"
    property string theme: "periodico"
    property bool expanded: false
    property bool loading: false
    property string save_status: "Guardado"
    property int selectedImage: -1
    property int insertionPosition: 0
    property var imageEntries: []
    readonly property bool dark: theme === "gris"
    readonly property color paper: dark ? "#252a32" : theme === "postit" ? paper_color : "#f6f2e9"
    readonly property color ink: dark ? "#edece8" : "#302f2b"
    readonly property color muted: dark ? "#a8afb9" : "#79766d"
    readonly property color line: dark ? "#414751" : "#d9d3c6"
    readonly property color accent: dark ? "#c4d6ad" : "#4b6441"
    readonly property color hoverPaper: dark ? "#353c46" : "#e9e3d6"
    modal: false; dim: false; focus: true
    closePolicy: Popup.NoAutoClose
    width: expanded ? hostWindow.width - 32 : Math.min(400, Math.max(320, hostWindow.width * 0.40))
    x: expanded ? 16 : hostWindow.width - width - 12
    y: expanded ? 16 : hostWindow.reading_mode ? 54 : 96
    height: hostWindow.height - y - (expanded ? 16 : 12)
    padding: hostWindow.height < 620 ? 12 : 18; spacing: 12
    onReaderIdentityChanged: navigation_timer.restart()
    onWidthChanged: image_layout_timer.restart()
    onClosed: save_timer.stop()

    function show_note(note) {
        if (visible && note_id !== note.id && !save()) return;
        save_timer.stop(); loading = true;
        note_id = note.id; ownerIdentity = readerIdentity;
        paper_color = note.color; theme = note.theme || "postit";
        selectedImage = -1; imageEntries = [];
        note_text.text = backend.note_html(note.id);
        expanded = false; save_status = "Guardado";
        loading = false; open(); image_layout_timer.restart(); note_text.forceActiveFocus();
    }
    function save() {
        save_timer.stop();
        if (loading || !note_id) return true;
        const ok = backend.save_note_document(note_id, note_text.textDocument, paper_color, theme);
        save_status = ok ? "Guardado" : "No se pudo guardar";
        return ok;
    }
    function changed() {
        image_layout_timer.restart();
        if (!loading && visible) { save_status = "Guardando…"; save_timer.restart(); }
    }
    function finish() { if (save()) close(); }
    function selected_entry() { return imageEntries.find(entry => entry.position === selectedImage); }
    function change_image(alignment, width) {
        const entry = selected_entry();
        if (!entry) return;
        selectedImage = backend.note_change_image(note_text.textDocument, entry.position, entry.position, alignment, width);
        image_layout_timer.restart();
    }
    function insert_image(source) {
        selectedImage = backend.note_insert_image(note_text.textDocument, insertionPosition, source, "left");
        if (selectedImage >= 0) note_text.cursorPosition = selectedImage + 1;
        note_text.forceActiveFocus(); image_layout_timer.restart();
    }
    function move_image(position, target, alignment) {
        selectedImage = backend.note_change_image(note_text.textDocument, position, target, alignment, 0);
        image_layout_timer.restart();
    }
    function remove_image(position) {
        backend.note_remove_image(note_text.textDocument, position);
        selectedImage = -1; image_layout_timer.restart(); note_text.forceActiveFocus();
    }

    component NoteTool: Button {
        id: tool
        property bool chosen: false
        property bool primary: false
        property bool danger: false
        property string hint: text
        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
        padding: 8; leftPadding: 11; rightPadding: 11
        implicitHeight: 32
        Accessible.name: hint
        background: Rectangle {
            radius: 8
            color: tool.primary ? editor.accent : tool.chosen || tool.down || tool.hovered ? editor.hoverPaper : "transparent"
            border.width: tool.visualFocus || tool.chosen ? 1 : 0
            border.color: tool.visualFocus ? editor.accent : editor.line
            Behavior on color { ColorAnimation { duration: 100 } }
        }
        contentItem: Text {
            text: tool.text; font.pixelSize: 12; font.weight: tool.chosen || tool.primary ? Font.DemiBold : Font.Normal
            color: tool.danger ? (editor.dark ? "#f39494" : "#b14a4a") : tool.primary ? (editor.dark ? "#252a32" : "#ffffff") : editor.ink
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        }
        ToolTip.visible: hovered; ToolTip.text: hint; ToolTip.delay: 500
    }

    background: Rectangle {
        color: editor.paper; radius: 14; border.color: editor.line
        Rectangle { x: 20; y: 0; width: 44; height: 4; radius: 2; color: editor.paper_color }
    }
    header: Item {
        implicitHeight: editor.hostWindow.height < 620 ? 64 : 78
        Column {
            x: 20; y: 20; spacing: 4
            Text { text: "CUADERNO PERSONAL"; font.pixelSize: 9; font.letterSpacing: 1.4; color: editor.muted }
            Text { text: "Mi nota"; font.family: "Serif"; font.pixelSize: 23; color: editor.ink }
        }
        Row {
            anchors.right: parent.right; anchors.rightMargin: 12; anchors.top: parent.top; anchors.topMargin: 24; spacing: 2
            NoteTool { objectName: "expandNote"; text: editor.expanded ? "↙" : "⛶"; hint: editor.expanded ? "Volver junto al artículo" : "Ampliar nota"; onClicked: editor.expanded = !editor.expanded }
            NoteTool { objectName: "closeNote"; text: "×"; hint: "Guardar y cerrar"; onClicked: editor.finish() }
        }
    }
    contentItem: ColumnLayout {
        spacing: editor.hostWindow.height < 620 ? 6 : 12
        RowLayout {
            Layout.fillWidth: true; spacing: 2
            Repeater {
                model: [{key: "periodico", name: "Periódico"}, {key: "gris", name: "Gris"}, {key: "postit", name: "Post-it"}]
                delegate: NoteTool {
                    required property var modelData
                    objectName: "noteTheme_" + modelData.key
                    Layout.fillWidth: true; text: modelData.name; chosen: editor.theme === modelData.key
                    onClicked: { editor.theme = modelData.key; editor.save(); }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            Repeater {
                model: editor.markerColors
                delegate: Button {
                    required property var modelData
                    implicitWidth: 19; implicitHeight: 19; padding: 0
                    Accessible.name: "Color del post-it: " + modelData.name
                    background: Rectangle { color: modelData.color; radius: 10; border.width: editor.paper_color === modelData.color ? 2 : 0; border.color: editor.muted }
                    contentItem: Item {}
                    onClicked: { editor.paper_color = modelData.color; editor.save(); }
                    ToolTip.visible: hovered; ToolTip.text: modelData.name
                }
            }
            Item { Layout.fillWidth: true }
            Label { text: editor.save_status; color: editor.muted; font.pixelSize: 10 }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: editor.line }
        Label {
            visible: !editor.expanded && editor.height > 500; text: "Tu artículo sigue disponible a la izquierda."
            Layout.fillWidth: true; wrapMode: Text.Wrap; color: editor.muted; font.pixelSize: 11
        }
        ScrollView {
            id: note_scroll
            objectName: "noteScroll"
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            contentWidth: availableWidth
            TextArea {
                id: note_text; objectName: "noteText"
                width: note_scroll.availableWidth
                height: Math.max(note_scroll.availableHeight, contentHeight + topPadding + bottomPadding)
                padding: 2; bottomPadding: 24
                placeholderText: "Escribe, conecta ideas, haz preguntas…"
                placeholderTextColor: editor.muted; color: editor.ink; selectionColor: editor.accent
                selectedTextColor: editor.dark ? "#252a32" : "#ffffff"
                wrapMode: TextEdit.Wrap; textFormat: TextEdit.RichText; selectByMouse: true; persistentSelection: true
                font.family: "Serif"; font.pixelSize: 16
                background: Item {}
                onTextChanged: editor.changed()
                onContentHeightChanged: image_layout_timer.restart()
                onWidthChanged: image_layout_timer.restart()
                Keys.onEscapePressed: { if (editor.selectedImage >= 0) editor.selectedImage = -1; else editor.finish(); }
                Repeater {
                    model: editor.imageEntries
                    delegate: Rectangle {
                        id: image_handle
                        required property var modelData
                        objectName: "noteImageHandle"
                        x: note_text.leftPadding + modelData.x; y: note_text.topPadding + modelData.y
                        width: modelData.width; height: modelData.height
                        color: "transparent"; radius: 3
                        border.width: editor.selectedImage === modelData.position ? 1 : 0; border.color: editor.accent
                        MouseArea {
                            anchors.fill: parent; cursorShape: drag.active ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                            preventStealing: true; drag.target: image_handle
                            property int startPosition: -1
                            property string startAlignment: "left"
                            onPressed: { startPosition = image_handle.modelData.position; startAlignment = image_handle.modelData.alignment; editor.selectedImage = startPosition; }
                            onReleased: function(mouse) {
                                if (drag.active) {
                                    const position = note_text.positionAt(image_handle.x + mouse.x, image_handle.y + mouse.y);
                                    editor.move_image(startPosition, position, startAlignment);
                                }
                            }
                            onCanceled: image_layout_timer.restart()
                            ToolTip.visible: containsMouse; ToolTip.text: "Arrastra para mover. Clic para ajustar el texto."; hoverEnabled: true; ToolTip.delay: 600
                        }
                        Button {
                            objectName: "removeNoteImage"; anchors.right: parent.right; anchors.top: parent.top
                            width: 20; height: 20; padding: 0
                            topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
                            Accessible.name: "Eliminar imagen"
                            background: Rectangle { radius: 10; color: parent.hovered ? "#c23b43" : "#a94c52" }
                            contentItem: Text { text: "×"; color: "white"; font.pixelSize: 16; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                            onClicked: editor.remove_image(image_handle.modelData.position)
                            ToolTip.visible: hovered; ToolTip.text: "Eliminar imagen"
                        }
                    }
                }
            }
        }
        ColumnLayout {
            visible: editor.selectedImage >= 0 && !!editor.selected_entry()
            Layout.fillWidth: true; spacing: 4
            Label { text: "AJUSTE DE IMAGEN"; color: editor.muted; font.pixelSize: 9; font.letterSpacing: 1 }
            RowLayout {
                Layout.fillWidth: true; spacing: 2
                Repeater {
                    model: [{key: "left", label: "Izquierda"}, {key: "right", label: "Derecha"}, {key: "inline", label: "En línea"}]
                    delegate: NoteTool {
                        required property var modelData
                        objectName: "noteImageAlign_" + modelData.key
                        Layout.fillWidth: true; leftPadding: 7; rightPadding: 7; text: modelData.label
                        chosen: !!editor.selected_entry() && editor.selected_entry().alignment === modelData.key
                        onClicked: editor.change_image(modelData.key, 0)
                    }
                }
                NoteTool { text: "−"; hint: "Reducir imagen"; onClicked: { const entry = editor.selected_entry(); if (entry) editor.change_image(entry.alignment, Math.max(48, entry.width * 0.8)); } }
                NoteTool { text: "+"; hint: "Ampliar imagen"; onClicked: { const entry = editor.selected_entry(); if (entry) editor.change_image(entry.alignment, Math.min(note_text.width - 16, entry.width * 1.25)); } }
            }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: editor.line }
        RowLayout {
            Layout.fillWidth: true
            NoteTool { objectName: "insertNoteImage"; text: "＋ Imagen"; primary: true; hint: "Insertar imagen en el cursor"; onClicked: { editor.insertionPosition = note_text.cursorPosition; note_image_file.open(); } }
            Label { text: "en el cursor"; color: editor.muted; font.pixelSize: 10; Layout.fillWidth: true }
            NoteTool { objectName: "deleteNote"; text: "⌫"; danger: true; hint: "Eliminar nota"; onClicked: delete_note_dialog.open() }
        }
    }
    Timer { id: navigation_timer; interval: 0; onTriggered: if (editor.visible && editor.readerIdentity !== editor.ownerIdentity) editor.finish() }
    Timer { id: save_timer; interval: 450; onTriggered: editor.save() }
    Timer { id: image_layout_timer; interval: 0; onTriggered: if (editor.visible) editor.imageEntries = backend.note_image_layout(note_text.textDocument) }
    FileDialog { options: FileDialog.DontUseNativeDialog;
        id: note_image_file; title: "Insertar imagen en la nota"
        nameFilters: ["Imágenes (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"]
        onAccepted: { const source = backend.import_note_image(selectedFile.toString()); if (source) editor.insert_image(source); }
    }
    Dialog {
        id: delete_note_dialog; anchors.centerIn: parent; modal: true; title: "Eliminar nota"
        standardButtons: Dialog.Yes | Dialog.No
        Label { text: "Se eliminarán el texto y las imágenes de esta nota."; wrapMode: Text.Wrap; width: Math.min(300, editor.width - 48) }
        onAccepted: { save_timer.stop(); if (backend.delete_note(editor.note_id)) { editor.note_id = ""; editor.close(); } }
    }
}
