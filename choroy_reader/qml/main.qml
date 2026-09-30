import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: window
    objectName: "mainWindow"
    visible: true
    width: 900; height: 760
    minimumWidth: 700; minimumHeight: 500
    onClosing: function(close) { if (note_editor.visible) { close.accepted = note_editor.save(); } }
    title: "Choroy Reader"
    FontLoader { id: interface_font; source: "../../assets/fonts/DejaVuSans.ttf" }
    property var s: backend.state
    property var p: s.palette
    palette.window: p.panel
    palette.windowText: p.text
    palette.text: p.text
    palette.buttonText: p.text
    palette.button: p.card
    palette.base: p.panel
    palette.alternateBase: p.hover
    palette.highlight: p.accent
    palette.highlightedText: p.accent_text
    palette.mid: p.border
    palette.dark: p.border
    palette.light: p.hover
    property real feed_scroll: 0
    property bool sidebar_visible: true
    property bool shortcuts_open: false
    property bool reading_mode: false
    property bool forest_active: s.page === "forest" && !reader_open
    property int forest_previous_visibility: Window.Windowed
    property bool forest_window_ready: false
    Component.onCompleted: Qt.callLater(function() { forest_window_ready = true; if (forest_active) sync_forest_window(); })
    onForest_activeChanged: { if (forest_window_ready) sync_forest_window(); }
    function sync_forest_window() {
        if (forest_active) {
            forest_previous_visibility = visibility;
            showFullScreen();
            forest_intro.opacity = 1;
        } else {
            forest_intro.opacity = 0;
            visibility = forest_previous_visibility;
        }
    }
    Shortcut {
        sequence: "Escape"; context: Qt.WindowShortcut
        enabled: window.forest_active && !forest_delete.visible
        onActivated: {
            if (forest_intro.opacity > 0) { forest_intro.opacity = 0; }
            else backend.navigate("feed", "", "");
        }
    }
    Rectangle {
        id: forest_intro; objectName: "forestIntro"
        anchors.fill: parent; z: 2000; color: p.bg
        opacity: 0; visible: opacity > 0; enabled: visible
        Behavior on opacity { NumberAnimation { duration: 650; easing.type: Easing.InOutQuad } }
        MouseArea { anchors.fill: parent; acceptedButtons: Qt.LeftButton; cursorShape: Qt.PointingHandCursor; onClicked: forest_intro.opacity = 0 }
        ColumnLayout {
            anchors.centerIn: parent; width: Math.min(1000, parent.width - 40); spacing: 16
            Image { objectName: "forestIntroImage"; source: s.forest_image; fillMode: Image.PreserveAspectFit; Layout.alignment: Qt.AlignHCenter; Layout.preferredWidth: Math.min(840, parent.width, Math.max(0, window.height - forest_intro_text.implicitHeight - 56) * 1.5); Layout.preferredHeight: Layout.preferredWidth / 1.5 }
            ColumnLayout {
                id: forest_intro_text
                Layout.alignment: Qt.AlignHCenter
                Layout.fillWidth: true; Layout.maximumWidth: 600; spacing: 16
            Label { textFormat: Text.PlainText; text: "EL BOSQUE"; color: p.accent; font.letterSpacing: 3; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
            Label { textFormat: Text.PlainText; text: "Cuidar lo que te rodea también es elegir qué dejas crecer."; color: p.text; font.pixelSize: 28; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
            Label { textFormat: Text.PlainText; text: "Haz espacio para las fuentes que te aportan."; color: p.muted; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
            Action { objectName: "forestIntroStart"; text: "Haz clic para entrar en El Bosque"; Layout.alignment: Qt.AlignHCenter; onClicked: { forest_intro.opacity = 0; } }
            }
        }
    }
    property int previous_visibility: Window.Windowed
    property bool reader_open: !!s.reader.link
    onReader_openChanged: { if (!reader_open) leave_reading_mode(); }
    onVisibilityChanged: function() {
        if (window.reading_mode && (window.visibility === Window.Windowed || window.visibility === Window.Maximized))
            window.reading_mode = false;
    }
    function enter_reading_mode() {
        if (!reader_open || reading_mode) return;
        previous_visibility = visibility;
        reading_mode = true;
        showFullScreen();
    }
    function leave_reading_mode() {
        if (!reading_mode) return;
        reading_mode = false;
        visibility = previous_visibility;
    }
    Shortcut {
        sequence: "Escape"; context: Qt.WindowShortcut
        enabled: window.reading_mode && !image_viewer.visible && !quote_dialog.visible && !note_editor.visible
        onActivated: window.leave_reading_mode()
    }
    function go_back() {
        if (note_editor.visible) {
            if (note_editor.save()) note_editor.close();
            return;
        }
        backend.go_back();
    }
    Shortcut { sequences: [StandardKey.Back]; onActivated: window.go_back() }
    MouseArea {
        objectName: "mouseBackNavigation"
        anchors.fill: parent; z: 1000
        acceptedButtons: Qt.BackButton
        onClicked: window.go_back()
    }
    property bool settings_open: false
    property var expanded_categories: ({})
    property var managed_categories: ({})
    property string management_query: ""
    property string management_target: ""
    function manage_category(cat, src) {
        management_query = "";
        management_target = cat.name;
        const next = {}; next[cat.name] = true; managed_categories = next;
        backend.navigate("sources", "", "");
        if (src) source_dialog.edit(cat.index, src);
    }
    function source_for(url) {
        for (const cat of s.categories)
            for (const src of cat.sources)
                if (src.url === url) return {cat: cat, src: src};
        return null;
    }
    function source_matches(src) {
        const normalize = value => value.toLocaleLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
        return normalize(src.name + " " + src.url + " " + src.feed).includes(normalize(management_query).trim());
    }
    component ReorderArea: MouseArea {
        id: reorder
        property string kind
        property string entry_key
        signal activate()
        signal context()
        signal moved(string from_key)
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: drag.active ? Qt.ClosedHandCursor : Qt.PointingHandCursor
        drag.target: ghost
        onClicked: mouse => { if (mouse.button === Qt.RightButton) context(); else activate(); }
        onReleased: { ghost.Drag.drop(); ghost.x = 0; ghost.y = 0; }
        onCanceled: { ghost.Drag.cancel(); ghost.x = 0; ghost.y = 0; }
        Item {
            id: ghost; width: reorder.width; height: reorder.height
            Drag.active: reorder.drag.active
            Drag.source: reorder
            Drag.keys: [reorder.kind]
            Drag.hotSpot.x: width / 2; Drag.hotSpot.y: height / 2
        }
        DropArea {
            anchors.fill: parent; keys: [reorder.kind]
            onDropped: drop => { if (drop.source !== reorder) { const key = drop.source.entry_key; Qt.callLater(() => reorder.moved(key)); drop.accept(); } }
            Rectangle { anchors.fill: parent; color: "transparent"; border.width: 2; border.color: p.accent; visible: parent.containsDrag }
        }
    }
    color: p.bg
    font.family: interface_font.name
    font.pixelSize: 13

    component Action: Button {
        id: control
        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
        property bool active: false
        property bool compact: false
        property string symbol: ""
        property bool warning: false
        property bool shortcut: false
        property string favicon: ""
        leftPadding: 12; rightPadding: 12; topPadding: compact ? 5 : 9; bottomPadding: compact ? 5 : 9
        implicitHeight: Math.max(32, contentItem.implicitHeight + topPadding + bottomPadding)
        background: Rectangle { radius: 6; color: control.warning ? (p.light ? "#f0dcdc" : "#39272a") : control.down ? Qt.lighter(p.hover, 1.35) : control.hovered ? Qt.lighter(p.hover, 1.2) : control.shortcut ? p.hover : control.active ? p.selection : "transparent"; border.color: control.shortcut ? p.border : control.visualFocus ? p.accent : "transparent" }
        contentItem: RowLayout { spacing: 10
            Image { visible: control.favicon.length > 0; source: control.favicon; Layout.preferredWidth: 18; Layout.preferredHeight: 18; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true }
            Glyph { visible: control.symbol.length > 0; kind: control.symbol; ink: control.active ? (p.light ? p.forest : p.accent) : p.text; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
            Text { textFormat: Text.PlainText; Layout.fillWidth: true; text: control.text; color: !control.enabled ? p.muted : control.shortcut ? p.text : control.active ? (p.light ? p.text : p.accent) : p.text; font: control.font; wrapMode: Text.Wrap; verticalAlignment: Text.AlignVCenter }
        }
    }
    component Search: TextField {
        id: field
        implicitHeight: 38
        leftPadding: 14; rightPadding: 14
        color: p.text; placeholderTextColor: p.muted; selectionColor: p.accent; selectedTextColor: p.accent_text
        background: Rectangle { color: p.hover; radius: 9; border.width: 1; border.color: field.activeFocus ? p.accent : p.border }
    }
    component SettingsChoice: ComboBox {
        id: choice
        implicitHeight: 38
        background: Rectangle { radius: 8; color: p.hover; border.color: choice.activeFocus ? p.accent : p.border }
        contentItem: Text { textFormat: Text.PlainText; text: choice.displayText; color: p.text; leftPadding: 12; rightPadding: 30; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
        indicator: Text { textFormat: Text.PlainText; text: "⌄"; color: p.accent; x: parent.width - width - 12; y: (parent.height - height)/2 }
        delegate: ItemDelegate {
            required property int index
            required property var modelData
            width: choice.width
            contentItem: Text { textFormat: Text.PlainText; text: modelData; color: choice.currentIndex === index ? p.accent : p.text; elide: Text.ElideRight }
            background: Rectangle { color: parent.hovered || choice.currentIndex === parent.index ? p.hover : p.panel }
        }
        popup: Popup {
            y: choice.height + 4; width: choice.width; padding: 4
            implicitHeight: Math.min(contentItem.implicitHeight + 8, 300)
            background: Rectangle { color: p.panel; radius: 8; border.color: p.border }
            contentItem: ListView { clip: true; implicitHeight: contentHeight; model: choice.popup.visible ? choice.delegateModel : null; currentIndex: choice.highlightedIndex; ScrollIndicator.vertical: ScrollIndicator {} }
        }
    }
    component Check: CheckBox {
        id: check
        spacing: 10
        contentItem: Text { textFormat: Text.PlainText; text: check.text; color: p.text; leftPadding: check.indicator.width + check.spacing; verticalAlignment: Text.AlignVCenter; wrapMode: Text.Wrap }
        indicator: Rectangle { x: 0; y: (check.height-height)/2; width: 20; height: 20; radius: 5; color: check.checked ? p.accent : p.hover; border.color: p.border
            Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: check.checked ? "✓" : ""; color: p.accent_text }
        }
    }
    component Glyph: Item {
        id: glyph
        property string kind: "save"
        property color ink: p.accent
        property bool filled: false
        implicitWidth: 20; implicitHeight: 20
        onKindChanged: drawing.requestPaint()
        onInkChanged: drawing.requestPaint()
        onFilledChanged: drawing.requestPaint()
        Canvas { id: drawing; anchors.fill: parent; antialiasing: true
            onPaint: {
                const c = getContext("2d"); c.reset(); c.scale(width/24,height/24); c.strokeStyle=glyph.ink; c.fillStyle=glyph.ink; c.lineWidth=1.7; c.lineJoin="round"; c.lineCap="round";
                c.beginPath();
                if (glyph.kind === "save") { c.moveTo(6,3);c.lineTo(18,3);c.lineTo(18,21);c.lineTo(12,16);c.lineTo(6,21);c.closePath(); if(glyph.filled)c.fill();c.stroke(); }
                else if (glyph.kind === "read") { c.moveTo(4,12);c.lineTo(9,17);c.lineTo(20,6);c.stroke(); }
                else if (glyph.kind === "unread") { c.arc(12,12,8,0,Math.PI*2);c.stroke();c.beginPath();c.arc(12,12,3,0,Math.PI*2);c.fill(); }
                else if (glyph.kind === "dismiss") { c.moveTo(7,3);c.lineTo(15,2);c.lineTo(21,8);c.lineTo(20,16);c.lineTo(14,22);c.lineTo(5,19);c.lineTo(2,11);c.closePath();c.moveTo(7,3);c.lineTo(9,10);c.lineTo(2,11);c.moveTo(9,10);c.lineTo(15,7);c.lineTo(21,8);c.moveTo(9,10);c.lineTo(12,16);c.lineTo(5,19);c.moveTo(12,16);c.lineTo(20,16);c.moveTo(12,16);c.lineTo(14,22);c.stroke(); }
                else if (glyph.kind === "archive") { c.rect(3,4,18,5);c.moveTo(5,9);c.lineTo(5,21);c.lineTo(19,21);c.lineTo(19,9);c.moveTo(9,13);c.lineTo(15,13);c.stroke(); }
                else if (glyph.kind === "delete") { c.moveTo(4,6);c.lineTo(20,6);c.moveTo(9,6);c.lineTo(9,3);c.lineTo(15,3);c.lineTo(15,6);c.moveTo(6,6);c.lineTo(7,21);c.lineTo(17,21);c.lineTo(18,6);c.moveTo(10,10);c.lineTo(10,17);c.moveTo(14,10);c.lineTo(14,17);c.stroke(); }
                else if (glyph.kind === "articles") { c.rect(3,3,18,18);c.moveTo(7,7);c.lineTo(17,7);c.moveTo(7,11);c.lineTo(17,11);c.moveTo(7,15);c.lineTo(11,15);c.moveTo(7,18);c.lineTo(17,18);c.stroke(); }
                else { c.moveTo(12,3);c.lineTo(12,15);c.moveTo(7,10);c.lineTo(12,15);c.lineTo(17,10);c.moveTo(4,16);c.lineTo(4,21);c.lineTo(20,21);c.lineTo(20,16);c.stroke();if(glyph.filled){c.beginPath();c.arc(20,4,3,0,Math.PI*2);c.fill();} }
            }
        }
    }
    component IconAction: Button {
        id: icon_control
        property string kind: "save"
        property bool filled: false
        property string hint: ""
        property bool stateActive: filled
        implicitWidth: 34; implicitHeight: 34; padding: 7
        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
        Layout.preferredWidth: 34; Layout.preferredHeight: 34
        Layout.fillWidth: false; Layout.fillHeight: false
        Layout.minimumWidth: 34; Layout.maximumWidth: 34
        Layout.minimumHeight: 34; Layout.maximumHeight: 34
        Accessible.name: hint
        background: Rectangle { anchors.centerIn: parent; width: 34; height: 34; radius: 6; color: icon_control.stateActive ? p.forest : icon_control.hovered ? p.hover : p.card; border.width: icon_control.stateActive ? 2 : 1; border.color: icon_control.stateActive ? p.accent : icon_control.visualFocus ? p.accent : p.border }
        contentItem: Item {
            Glyph { anchors.centerIn: parent; width: 20; height: 20; kind: icon_control.kind; ink: icon_control.stateActive ? "#ffffff" : icon_control.kind === "delete" ? p.danger : p.muted; filled: icon_control.filled; opacity: icon_control.enabled ? 1 : 0.4 }
        }
        ToolTip.visible: hovered; ToolTip.text: hint; ToolTip.delay: 400
    }
    component RadarBadge: Rectangle {
        id: radar_badge
        required property var article
        property color radar_color: s.theme === "periodico" ? "#62834b" : p.accent
        HoverHandler { id: radar_hover }
        visible: radar_badge.article.radar > 0 && !radar_badge.article.dismissed
        Layout.fillWidth: true
        implicitHeight: radar_badge_text.implicitHeight + 16
        radius: 8; color: p.hover; border.color: radar_badge.radar_color
        Rectangle {
            anchors.fill: parent; radius: parent.radius; color: radar_badge.radar_color
            opacity: 0.08
            SequentialAnimation on opacity {
                running: radar_badge.visible && window.visible
                loops: Animation.Infinite
                NumberAnimation { from: 0.08; to: 0.28; duration: 1200; easing.type: Easing.InOutSine }
                NumberAnimation { from: 0.28; to: 0.08; duration: 1200; easing.type: Easing.InOutSine }
            }
        }
        Label { textFormat: Text.PlainText;
            id: radar_badge_text
            anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            anchors.margins: 8
            text: !radar_badge.article.radar ? "◎ Radar · Sin coincidencias" : radar_hover.hovered ? "◎ Radar · " + (radar_badge.article.radar_detected || []).join(", ") : "◎ Radar detectado · " + radar_badge.article.interests + (radar_badge.article.interests === 1 ? " interés" : " intereses") + " · " + radar_badge.article.mentions + (radar_badge.article.mentions === 1 ? " mención" : " menciones")
            color: radar_badge.radar_color; font.bold: true; font.pixelSize: 11; elide: Text.ElideRight
        }
    }

    component SectionTitle: Label { textFormat: Text.PlainText; color: p.text; font.pixelSize: 17; font.bold: true; wrapMode: Text.Wrap }

    ColumnLayout {
        anchors.fill: parent; spacing: 0
        Rectangle {
            objectName: "readingModeBar"
            visible: window.reading_mode
            Layout.fillWidth: true; Layout.preferredHeight: 52; color: p.bg
            Action {
                objectName: "exitReadingMode"
                text: "Salir del modo lectura · Esc"
                anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                onClicked: window.leave_reading_mode()
            }
        }
        Rectangle {
            objectName: "appHeader"; visible: !window.sidebar_visible && !window.reading_mode && !window.forest_active
            Layout.fillWidth: true; Layout.preferredHeight: 44; color: p.bg
            Action {
                objectName: "sidebarToggle"
                anchors.left: parent.left; anchors.leftMargin: 14; anchors.verticalCenter: parent.verticalCenter
                text: "☰"; onClicked: window.sidebar_visible = !window.sidebar_visible
                Accessible.name: window.sidebar_visible ? "Ocultar menú lateral" : "Mostrar menú lateral"
                ToolTip.visible: hovered; ToolTip.text: Accessible.name
            }

        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
            Rectangle {
                objectName: "sidebarPanel"; visible: window.sidebar_visible && !window.reading_mode && !window.forest_active && !note_editor.visible
                Layout.preferredWidth: 248; Layout.fillHeight: true; color: p.panel
                ColumnLayout {
                    anchors.fill: parent; spacing: 2
                    RowLayout {
                        Layout.fillWidth: true; Layout.margins: 16; spacing: 10
                        Image { objectName: "appLogo"; source: s.logo; Layout.preferredWidth: 44; Layout.preferredHeight: 44; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true }
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 3
                            Label { textFormat: Text.PlainText; text: "Choroy Reader"; color: p.text; font.bold: true; font.pixelSize: 16 }
                            Label { textFormat: Text.PlainText; text: "Tu lector, tu bosque."; color: p.muted; font.pixelSize: 11 }
                        }
                        Action { objectName: "sidebarHide"; text: "‹"; compact: true; Accessible.name: "Ocultar menú lateral"; onClicked: window.sidebar_visible = false }
                    }
                    ScrollView {
                        id: side_scroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                        contentWidth: availableWidth
                        ColumnLayout {
                            width: side_scroll.availableWidth; spacing: 4
                            Action { objectName: "articlesNavigation"; Layout.preferredHeight: 38; symbol: "articles"; text: "Todos los artículos"; active: s.page === "feed" && s.category === ""; Layout.fillWidth: true; Layout.margins: 14; onClicked: backend.navigate("feed", "", "") }
                            Label { textFormat: Text.PlainText; text: "BIBLIOTECA"; color: p.muted; font.pixelSize: 10; font.bold: true; Layout.leftMargin: 22; Layout.topMargin: 2; Layout.bottomMargin: 2 }
                            Action { symbol: "save"; text: "Guardados"; active: s.page === "guardados"; Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; onClicked: backend.navigate("guardados", "", "") }
                            Action { symbol: "articles"; text: "Historial"; active: s.page === "historial"; Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; onClicked: backend.navigate("historial", "", "") }
                            Action { symbol: "archive"; text: "Archivados"; active: s.page === "archivados"; Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; onClicked: backend.navigate("archivados", "", "") }
                            Action { symbol: "download"; text: "Descargas"; active: s.page === "descargas"; Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; onClicked: backend.navigate("descargas", "", "") }
                            RowLayout {
                                Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                                Label { textFormat: Text.PlainText; text: "Radar de intereses"; color: p.text; Layout.fillWidth: true }
                                Switch {
                                    id: radar_switch; objectName: "radar_switch"; checked: s.radar; onClicked: backend.toggle_radar(); padding: 0
                                    indicator: Rectangle { width: 42; height: 24; radius: 12; color: radar_switch.checked ? p.forest : "#777b82"
                                        Rectangle { x: radar_switch.checked ? 21 : 3; y: 3; width: 18; height: 18; radius: 9; color: "#f0f0f0"; Behavior on x { NumberAnimation { duration: 110 } } }
                                    }
                                }
                            }
                            Label { textFormat: Text.PlainText; text: "FUENTES"; color: p.muted; font.pixelSize: 10; font.bold: true; Layout.leftMargin: 22; Layout.topMargin: 16 }
                            Action { objectName: "forestNavigation"; text: "El Bosque"; favicon: s.forest_icon; active: s.page === "forest"; Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; onClicked: backend.navigate("forest", "", "") }
                            Action { text: "Gestionar fuentes"; symbol: "articles"; Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; onClicked: backend.navigate("sources", "", "") }
                            Item { height: 12; Layout.fillWidth: true }
                        }
                    }
                    Rectangle { Layout.fillWidth: true; Layout.margins: 18; height: 1; color: p.border }
                    ColumnLayout {
                        Layout.fillWidth: true; Layout.margins: 14; Layout.alignment: Qt.AlignTop; spacing: 1
                        Item {
                            id: settings_drawer; Layout.fillWidth: true
                            Layout.preferredHeight: window.settings_open ? settings_menu.implicitHeight : 0
                            opacity: window.settings_open ? 1 : 0; clip: true
                            Behavior on Layout.preferredHeight { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }
                            Behavior on opacity { NumberAnimation { duration: 130 } }
                            ColumnLayout {
                                id: settings_menu; width: parent.width; spacing: 1
                                Action { objectName: "designNavigation"; Layout.preferredHeight: 38; text: "Diseño"; active: s.page === "design"; Layout.fillWidth: true; onClicked: backend.navigate("design", "", "") }
                                Action { text: "Gestionar fuentes y categorías"; active: s.page === "sources"; Layout.fillWidth: true; onClicked: backend.navigate("sources", "", "") }
                                Action { text: "Configurar radar"; active: s.page === "radar"; Layout.fillWidth: true; onClicked: backend.navigate("radar", "", "") }
                                Action { text: "Almacenamiento"; active: s.page === "storage"; Layout.fillWidth: true; onClicked: backend.navigate("storage", "", "") }
                                Action { text: "Acerca de Choroy Reader"; active: s.page === "about"; Layout.fillWidth: true; onClicked: backend.navigate("about", "", "") }
                            }
                        }
                        Action {
                            objectName: "settingsToggle"; Layout.preferredHeight: 38
                            text: (window.settings_open ? "⌃  " : "⌄  ") + "Configuración"
                            active: window.settings_open || s.page === "design" || s.page === "sources" || s.page === "radar" || s.page === "storage" || s.page === "about"
                            Layout.fillWidth: true; onClicked: window.settings_open = !window.settings_open
                        }
                    }
                    Rectangle { Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22; height: 1; color: p.border }
                    RowLayout {
                        Layout.leftMargin: 18; Layout.rightMargin: 18; spacing: 8
                        Repeater { model: ["GitHub", "Instagram", "Mastodon"]
                            delegate: Button {
                                id: social_button
                                required property string modelData
                                implicitWidth: 34; implicitHeight: 34; padding: 0
                                Layout.minimumWidth: 34; Layout.maximumWidth: 34
                                Layout.minimumHeight: 34; Layout.maximumHeight: 34
                                topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
                                objectName: "social_" + modelData
                                Accessible.name: modelData + " del autor"
                                onClicked: backend.open_url(s.about.socials[modelData])
                                ToolTip.visible: hovered; ToolTip.text: modelData + " · " + s.about.socials[modelData]
                                background: Item {}
                                contentItem: Item {
                                  Canvas {
                                    anchors.centerIn: parent; width: 22; height: 22
                                    property color ink: social_button.hovered || social_button.visualFocus ? p.accent : p.muted
                                    Behavior on ink { ColorAnimation { duration: 140 } }
                                    onInkChanged: requestPaint()
                                    onPaint: {
                                        const c=getContext("2d");c.reset();c.scale(width/24,height/24);c.strokeStyle=ink;c.fillStyle=ink;c.lineWidth=1.7;c.lineJoin="round";
                                        if(social_button.modelData==="Instagram") {c.strokeRect(3,3,18,18);c.beginPath();c.arc(12,12,4,0,Math.PI*2);c.stroke();c.beginPath();c.arc(18,6,1,0,Math.PI*2);c.fill();}
                                        else if(social_button.modelData==="GitHub") {c.beginPath();c.moveTo(5,8);c.lineTo(5,3);c.lineTo(10,6);c.lineTo(14,6);c.lineTo(19,3);c.lineTo(19,8);c.bezierCurveTo(24,17,17,20,12,20);c.bezierCurveTo(7,20,0,17,5,8);c.stroke();c.moveTo(10,20);c.lineTo(10,24);c.moveTo(14,20);c.lineTo(14,24);c.stroke();}
                                        else {c.strokeRect(2,3,20,16);c.beginPath();c.moveTo(3,19);c.lineTo(6,23);c.lineTo(16,23);c.moveTo(6,15);c.lineTo(6,8);c.lineTo(9,7);c.lineTo(12,10);c.lineTo(15,7);c.lineTo(18,8);c.lineTo(18,15);c.moveTo(12,10);c.lineTo(12,15);c.stroke();}
                                    }
                                  }
                                }
                            }
                        }
                    }
                    Label { textFormat: Text.PlainText; text: s.radar_busy ? "Radar: analizando contenido…" : s.status; color: p.muted; wrapMode: Text.Wrap; font.pixelSize: 10; Layout.fillWidth: true; Layout.margins: 18 }
                }
            }
            Loader {
                id: main_loader; Layout.fillWidth: true; Layout.fillHeight: true
                sourceComponent: s.reader.link ? reader_page : s.page === "forest" ? forest_page : s.page === "about" ? about_page : s.page === "storage" ? storage_page : s.page === "design" ? design_page : s.page === "radar" ? radar_page : s.page === "sources" ? sources_page : feed_page
            }
            Item {
                visible: note_editor.visible && !note_editor.expanded
                Layout.preferredWidth: note_editor.width + 24; Layout.fillHeight: true
            }
        }
    }

    Component {
        id: feed_page
        ColumnLayout {
            spacing: 8
            RowLayout {
                Layout.fillWidth: true; Layout.margins: 14; spacing: 10
                Search { objectName: "titleSearch"; Layout.fillWidth: true; Layout.minimumWidth: 60; placeholderText: s.page === "guardados" && s.search_content ? "Buscar en títulos y contenido guardado" : "Buscar en títulos"; text: s.query; onTextEdited: title_search_delay.restart()
                    Timer { id: title_search_delay; interval: 180; onTriggered: backend.search_titles(parent.text) }
                }
                Button {
                    id: refresh_button; objectName: "refreshFeedButton"
                    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
                    text: s.refresh_cancelling ? "Cancelando…" : s.busy ? "Cancelar" : "Actualizar feed"
                    enabled: !s.refresh_cancelling; Layout.preferredHeight: 38
                    leftPadding: 14; rightPadding: 14
                    Accessible.name: s.busy ? "Cancelar actualización del feed" : "Actualizar feed"
                    onClicked: s.busy ? backend.cancel_refresh() : backend.refresh()
                    ToolTip.visible: hovered
                    ToolTip.text: s.busy ? "Cancelar actualización y conservar el feed anterior" : "Buscar nuevos artículos"
                    implicitWidth: Math.max(refresh_metrics.width, contentItem.implicitWidth) + leftPadding + rightPadding
                    TextMetrics { id: refresh_metrics; font.bold: true; text: "Actualizar feed" }
                    background: Rectangle {
                        radius: 10
                        color: s.busy ? "#287a42" : refresh_button.hovered ? "#343a40" : "#24282d"
                        opacity: !refresh_button.enabled ? 0.45 : refresh_button.down ? 0.7 : refresh_button.hovered ? 0.85 : 1
                        border.width: 1; border.color: s.busy ? "#72db91" : refresh_button.visualFocus ? p.accent : "#50565e"
                        Rectangle {
                            anchors.fill: parent; radius: parent.radius; color: "#72db91"; visible: s.busy
                            SequentialAnimation on opacity {
                                running: s.busy; loops: Animation.Infinite
                                NumberAnimation { from: 0.05; to: 0.25; duration: 650 }
                                NumberAnimation { from: 0.25; to: 0.05; duration: 650 }
                            }
                        }
                    }
                    contentItem: RowLayout {
                        spacing: 7
                        Text { textFormat: Text.PlainText;
                            text: "↻"; color: "#ffffff"; font.pixelSize: 22
                            visible: s.busy
                            RotationAnimator on rotation { from: 0; to: 360; duration: 1100; loops: Animation.Infinite; running: s.busy && !s.refresh_cancelling }
                        }
                        Text { textFormat: Text.PlainText;
                            text: refresh_button.text; font.bold: true; color: "#ffffff"
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
                Button {
                    id: offline_button; objectName: "downloadAllButton"
                    implicitWidth: Math.max(download_label_metrics.width, contentItem.implicitWidth) + leftPadding + rightPadding
                    TextMetrics { id: download_label_metrics; font.bold: true; text: "Modo offline" }
                    visible: s.page === "feed"
                    text: s.bulk_cancelling ? "Cancelando…" : s.bulk_busy ? "Cancelar" : "Modo offline"
                    enabled: !s.bulk_cancelling && (s.bulk_busy || s.total_articles > 0)
                    Layout.preferredHeight: 38
                    leftPadding: 12; rightPadding: 12
                    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
                    Accessible.name: s.bulk_busy ? "Cancelar descarga de todos los artículos" : "Descargar todo para leer sin conexión"
                    onClicked: s.bulk_busy ? backend.cancel_download_all() : bulk_dialog.open()
                    background: Rectangle {
                        radius: 10; color: s.bulk_busy ? "#287a42" : offline_button.hovered ? "#343a40" : "#24282d"
                        border.color: s.bulk_busy ? "#72db91" : offline_button.visualFocus ? p.accent : "#50565e"
                        Rectangle {
                            anchors.fill: parent; radius: parent.radius; color: "#72db91"
                            visible: s.bulk_busy; opacity: 0.08
                            SequentialAnimation on opacity {
                                running: s.bulk_busy; loops: Animation.Infinite
                                NumberAnimation { from: 0.08; to: 0.3; duration: 650 }
                                NumberAnimation { from: 0.3; to: 0.08; duration: 650 }
                            }
                        }
                        opacity: offline_button.enabled ? 1 : 0.45
                    }
                    contentItem: RowLayout {
                        spacing: 7
                        Item {
                            visible: s.bulk_busy
                            Layout.preferredWidth: 20; Layout.preferredHeight: 24
                            Glyph {
                                width: 20; height: 20; y: 2; kind: "download"
                                ink: offline_button.enabled ? "#ffffff" : "#a0a5ac"
                                SequentialAnimation on y {
                                    running: s.bulk_busy && !s.bulk_cancelling
                                    loops: Animation.Infinite
                                    NumberAnimation { from: -1; to: 4; duration: 550; easing.type: Easing.InQuad }
                                    NumberAnimation { from: 4; to: -1; duration: 250; easing.type: Easing.OutQuad }
                                }
                            }
                        }
                        Text { textFormat: Text.PlainText;
                            text: offline_button.text; font.bold: true
                            color: offline_button.enabled ? "#ffffff" : "#a0a5ac"
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        }
                    }
                    ToolTip.visible: hovered
                    ToolTip.text: s.bulk_busy ? "Cancelar y eliminar las descargas nuevas de esta operación. Se conservan las anteriores." : "Descarga todos los artículos cargados para leerlos sin conexión."
                }

            }
            Check { objectName: "searchSavedContent"; visible: s.page === "guardados"; text: "Buscar también en el contenido y traducciones guardadas"; checked: s.search_content; Layout.leftMargin: 18; onClicked: backend.set_search_content(checked) }
            Flickable {
                objectName: "categoryStrip"; visible: s.page === "feed"
                Layout.fillWidth: true; Layout.preferredHeight: 44; Layout.leftMargin: 18; Layout.rightMargin: 18
                clip: true; contentWidth: category_tabs.implicitWidth; contentHeight: height
                flickableDirection: Flickable.HorizontalFlick; boundsBehavior: Flickable.StopAtBounds
                ScrollBar.horizontal: ScrollBar {}
                Row {
                    id: category_tabs; spacing: 8
                    Action { text: "Todos"; compact: true; active: !s.category; onClicked: backend.navigate("feed", "", "") }
                    Repeater {
                        model: s.categories
                        delegate: Action {
                            id: category_tab; required property var modelData
                            objectName: "category_" + modelData.name
                            text: modelData.name; favicon: modelData.icon; compact: true; active: s.category === modelData.name
                            background: Rectangle { radius: 8; color: category_tab.active ? p.selection : category_tab.hovered ? p.hover : p.card; border.color: category_tab.active ? p.forest : p.border }
                            onClicked: backend.navigate("feed", modelData.name, "")
                            ReorderArea {
                                kind: "category"; entry_key: String(category_tab.modelData.index)
                                onActivate: category_tab.clicked()
                                onContext: category_tab_menu.popup()
                                onMoved: from_key => backend.move_category(Number(from_key), category_tab.modelData.index - Number(from_key))
                            }
                            Menu { id: category_tab_menu
                                MenuItem { objectName: "manage_category_" + category_tab.modelData.name; text: "Administrar categoría…"; onTriggered: window.manage_category(category_tab.modelData, null) }
                            }
                        }
                    }
                }
            }
            Flickable {
                visible: s.page === "feed" && !!s.category
                Layout.fillWidth: true; Layout.preferredHeight: 36; Layout.leftMargin: 18; Layout.rightMargin: 18
                clip: true; contentWidth: category_sources.implicitWidth; contentHeight: height
                flickableDirection: Flickable.HorizontalFlick; boundsBehavior: Flickable.StopAtBounds
                ScrollBar.horizontal: ScrollBar {}
                Row {
                    id: category_sources; spacing: 6
                    Repeater {
                        model: (s.categories.find(c => c.name === s.category) || {sources:[]}).sources
                        delegate: Action {
                            required property var modelData
                            text: modelData.name; favicon: modelData.icon; compact: true; active: s.source === modelData.url
                            onClicked: modelData.direct_access ? backend.open_url(modelData.url) : backend.navigate("feed", s.category, modelData.url)
                            TapHandler { acceptedButtons: Qt.RightButton; onTapped: horizontal_source_menu.popup() }
                            Menu { id: horizontal_source_menu
                                MenuItem { text: "Administrar fuente…"; onTriggered: window.manage_category(s.categories[modelData.category_index], modelData) }
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                visible: s.page === "feed" && s.link_sources.length > 0
                Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                spacing: 4
                Action {
                    objectName: "shortcutsToggle"
                    text: (window.shortcuts_open ? "⌃  " : "⌄  ") + "Atajos web · " + s.link_sources.length
                    compact: true; active: window.shortcuts_open
                    onClicked: window.shortcuts_open = !window.shortcuts_open
                    Accessible.name: window.shortcuts_open ? "Contraer atajos web" : "Desplegar atajos web"
                }
                ScrollView {
                    objectName: "shortcutsPanel"
                    visible: window.shortcuts_open
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(160, shortcut_list.implicitHeight)
                    clip: true; contentWidth: availableWidth
                    Column {
                        id: shortcut_list; width: parent.width; spacing: 4
                        Repeater {
                            model: s.link_sources
                            delegate: Action {
                                id: shortcut_button; objectName: "shortcut_" + modelData.name
                                required property var modelData
                                width: shortcut_list.width
                                text: modelData.name + " ↗"; favicon: modelData.icon; shortcut: true; compact: true
                                onClicked: backend.open_url(modelData.url)
                                ReorderArea {
                                    kind: "shortcut"; entry_key: shortcut_button.modelData.url
                                    onActivate: shortcut_button.clicked()
                                    onContext: shortcut_menu.popup()
                                    onMoved: from_key => backend.move_shortcut(from_key, shortcut_button.modelData.url)
                                }
                                Menu {
                                    id: shortcut_menu
                                    MenuItem { text: "Quitar atajo web"; onTriggered: backend.set_source_shortcut(shortcut_button.modelData.category_index, shortcut_button.modelData.index, "remove") }
                                    MenuItem { text: "Ir a administrar…"; onTriggered: window.manage_category(s.categories[shortcut_button.modelData.category_index], shortcut_button.modelData) }
                                }
                                ToolTip.visible: hovered; ToolTip.text: "Abrir sitio en el navegador"; ToolTip.delay: 500
                            }
                        }
                    }
                }
            }
            Label { textFormat: Text.PlainText; text: s.page === "descargas" ? "Descargas · Sin conexión" : s.page === "guardados" ? "Guardados" : s.page === "archivados" ? "Archivados" : s.page === "historial" ? "Historial" : s.page === "retirados" ? "Historial retirado · Recuperable durante 30 días" : s.category; visible: text.length > 0; color: p.accent; font.bold: true; Layout.leftMargin: 18 }
            RowLayout {
                visible: s.page === "guardados"; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; spacing: 8
                Label { textFormat: Text.PlainText; text: "Colección"; color: p.muted }
                ComboBox {
                    id: collection_filter; model: s.collections; textRole: "name"; Layout.fillWidth: true
                    currentIndex: Math.max(0, s.collections.findIndex(function(item) { return item.id === s.collection_filter; }))
                    onActivated: backend.set_collection_filter(model[currentIndex].id)
                }
                Action { text: "+ Colección"; compact: true; active: true; onClicked: { collection_name.text=""; collection_dialog.open(); } }
                Action { text: "Eliminar"; compact: true; visible: s.collection_filter.length > 0; onClicked: backend.delete_collection(s.collection_filter) }
            }
            Action {text: "Abrir sitio de la fuente ↗"; visible:s.source.length>0; Layout.leftMargin:18; compact:true; onClicked:backend.open_url(s.source)}
            Label { textFormat: Text.PlainText;
                visible: s.page === "historial"
                text: "Artículos recibidos, aunque ya no aparezcan en el RSS. Se conservan sus estados; para garantizar la lectura sin conexión, descárgalos."
                color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
            }
            GridView {
                id: feed_scroll_view; objectName: "feedGrid"
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.margins: 12
                clip: true; boundsBehavior: Flickable.StopAtBounds
                property int columns: Math.max(1, Math.min(s.columns, Math.floor(width / 290)))
                cellWidth: width / columns; cellHeight: columns === 1 ? 470 : 410
                cacheBuffer: cellHeight
                model: backend.articleModel
                // A model reset reorders/removes cards and resets GridView to the top.
                // Restore the row offset only while browsing the same list.
                property string scrollScope: JSON.stringify([s.page, s.category, s.source, s.query, s.collection_filter, s.search_content])
                property real resetOffset: 0
                property string resetScope: ""
                property bool restorePending: false
                Connections {
                    target: backend.articleModel
                    function onModelAboutToBeReset() {
                        if (!feed_scroll_view.restorePending) {
                            feed_scroll_view.resetOffset = feed_scroll_view.contentY;
                            feed_scroll_view.resetScope = feed_scroll_view.scrollScope;
                            feed_scroll_view.restorePending = true;
                        }
                    }
                    function onModelReset() {
                        Qt.callLater(feed_scroll_view.restoreAfterReset);
                    }
                }
                function restoreAfterReset() {
                    if (!restorePending) return;
                    restorePending = false;
                    if (resetScope !== scrollScope) return;
                    forceLayout();
                    contentY = Math.max(originY, Math.min(resetOffset, originY + Math.max(0, contentHeight - height)));
                }
                ScrollBar.vertical: ScrollBar {}
                Component.onCompleted: Qt.callLater(function(){contentY=Math.max(0, Math.min(window.feed_scroll, contentHeight-height));})
                Label { textFormat: Text.PlainText; text: s.busy ? "Cargando artículos e imágenes…" : s.query ? "No hay títulos que coincidan." : "No hay artículos en esta sección."; visible: feed_scroll_view.count === 0; color: p.muted; width: parent.width; padding: 20; wrapMode: Text.Wrap }
                delegate: Rectangle {
                    objectName: "feedCard"
                    id: card; required property var modelData
                    width: feed_scroll_view.cellWidth - 8; height: feed_scroll_view.cellHeight - 8; color: card_hover.hovered ? (p.light ? "#dfe2e5" : "#292e35") : p.card; radius: 10
                    border.color: card_hover.hovered ? p.accent : p.border; border.width: card_hover.hovered ? 2 : 1
                    Behavior on border.color { ColorAnimation { duration: 150 } }
                    Behavior on color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }
                    Rectangle {
                        anchors.fill: parent; radius: parent.radius; z: 1
                        visible: card.modelData.dismissed || card.modelData.seen
                        color: "#20242a"; opacity: 0.42
                    }
                    IconAction {
                        anchors.bottom: parent.bottom; anchors.right: parent.right; anchors.margins: 13; z: 2
                        kind: "dismiss"; stateActive: card.modelData.dismissed
                        hint: card.modelData.dismissed ? "Deshacer descarte" : "No me interesa · Enviar al final"
                        onClicked: backend.toggle_dismissed(card.modelData.link)
                    }
                    RowLayout {
                        anchors.left: parent.left; anchors.bottom: parent.bottom
                        anchors.leftMargin: 13; anchors.bottomMargin: 13; z: 2
                                spacing: 3
                                IconAction { kind: "read"; stateActive: card.modelData.seen; hint: card.modelData.seen ? "Marcar como no leído" : "Marcar como leído"; onClicked: backend.toggle_read(card.modelData.link) }
                                IconAction { kind: "archive"; stateActive: card.modelData.archived; hint: card.modelData.archived ? "Quitar de Archivados" : "Archivar artículo"; onClicked: backend.toggle_archived(card.modelData.link) }
                                IconAction { kind: "save"; filled: card.modelData.saved; hint: filled ? "Quitar guardado" : "Guardar artículo"; onClicked: backend.toggle_saved(card.modelData.link) }
                                IconAction { kind: card.modelData.downloaded ? "delete" : "download"; filled: card.modelData.downloaded; enabled: !card.modelData.downloading; hint: filled ? "Eliminar descarga" : "Descargar para leer sin conexión"; onClicked: backend.toggle_download(card.modelData.link) }
                            }
                    HoverHandler { id: card_hover }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; acceptedButtons: Qt.LeftButton | Qt.RightButton; onClicked: mouse => { if (mouse.button === Qt.RightButton) article_menu.popup(); else {window.feed_scroll=feed_scroll_view.contentY;backend.open_article(card.modelData.link);} } }
                    Menu {
                        id: article_menu
                        property var entry: window.source_for(card.modelData.source_url)
                        MenuItem { text: "Convertir fuente en atajo web (sin noticias)"; enabled: !!article_menu.entry; onTriggered: backend.set_source_shortcut(article_menu.entry.cat.index, article_menu.entry.src.index, "only") }
                        MenuItem { text: "Añadir fuente a atajos web (con noticias)"; enabled: !!article_menu.entry; onTriggered: backend.set_source_shortcut(article_menu.entry.cat.index, article_menu.entry.src.index, "add") }
                        MenuItem { text: "Ir a administrar fuente…"; enabled: !!article_menu.entry; onTriggered: window.manage_category(article_menu.entry.cat, article_menu.entry.src) }
                    }
                    ColumnLayout {
                        id: card_body; anchors.fill: parent; anchors.margins: 1; spacing: 0
                        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: feed_scroll_view.columns === 1 ? 200 : 150; color: p.hover; clip: true
                            Image { anchors.fill: parent; source: card.modelData.image; sourceSize.width: Math.ceil(width * 2); sourceSize.height: Math.ceil(height * 2); fillMode: Image.PreserveAspectCrop; asynchronous: true; smooth: true; mipmap: true }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; Layout.fillHeight: true; Layout.margins: 12; spacing: 8
                            RadarBadge { article: card.modelData }
                            RowLayout { Layout.fillWidth: true
                                Label { textFormat: Text.PlainText; text: card.modelData.source; color: p.light ? p.forest : p.text; font.bold: true; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                                Label { textFormat: Text.PlainText; text: card.modelData.date; color: p.muted; font.pixelSize: 10 }
                            }
                            Label { textFormat: Text.PlainText; text: "WEB · Publicación extraída"; visible: !!card.modelData.web_extracted; color: p.accent; font.pixelSize: 10; Layout.fillWidth: true }
                            Text { text: card.modelData.title_html; Layout.maximumHeight: font.pixelSize * 5; clip: true; textFormat: Text.RichText; color: card.modelData.seen || card.modelData.dismissed ? p.muted : p.text; font.bold: true; font.pixelSize: feed_scroll_view.columns === 1 ? 17 : 15; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            RowLayout { visible: card.modelData.show_translation && card.modelData.translation.length > 0; Layout.fillWidth: true; spacing: 6
                                Rectangle { width: 16; height: 16; radius: 8; color: "#c9293b"; Layout.alignment: Qt.AlignTop
                                    Rectangle { anchors.centerIn: parent; width: 15; height: 7; radius: 1; color: "#f6c645" }
                                }
                                Text { text: card.modelData.translation_html; Layout.maximumHeight: font.pixelSize * 5; clip: true; textFormat: Text.RichText; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 13 }
                            }
                            Action { visible: s.page === "retirados"; text: "Recuperar historial"; active: true; Layout.fillWidth: true; onClicked: backend.restore_history(card.modelData.link) }
                            Label { textFormat: Text.PlainText; visible: card.modelData.dismissed; text: "Descartado · No me interesa"; color: p.muted; font.bold: true; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            Item { Layout.fillHeight: true; Layout.minimumHeight: 0 }
                            Item { Layout.fillWidth: true; Layout.preferredHeight: 34 }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: reader_page
        ScrollView {
            id: reader_scroll; objectName: "reader_page"; clip: true; contentWidth: availableWidth
            contentHeight: reader_content.implicitHeight
            property bool marking: false
            property bool erasing: false
            property string marker_color: "#ffe88f"
            property int mark_anchor: 0
            property int menu_position: 0
            property string selected_quote: ""
            property int quote_parts_target: 0
            property var quote_parts: []
            property string quote_selection: article_text.selectedText.replace(/\u2029/g, "\n").trim()
            property string quote_joiner: "\n\n[…]\n\n"
            property int quote_used: Array.from(quote_selection).length + quote_parts.reduce((n,p) => n + Array.from(p.text).length, 0) + (quote_parts.length ? Array.from(quote_joiner).length : 0)
            property bool quote_overlap: quote_parts.some(p => article_text.selectionStart < p.end && article_text.selectionEnd > p.start)
            function begin_quote(parts) {
                marking = false; erasing = false; quote_parts = []; quote_parts_target = parts;
                article_text.deselect();
            }
            function accept_quote_part() {
                if (!quote_selection || quote_overlap || quote_used > 500) return;
                if (quote_parts_target === 2 && quote_parts.length === 0 && quote_used > 492) return;
                const parts = quote_parts.concat([{text:quote_selection, start:article_text.selectionStart, end:article_text.selectionEnd}]);
                if (parts.length < quote_parts_target) {
                    quote_parts = parts; article_text.deselect(); return;
                }
                parts.sort((a,b) => a.start-b.start);
                const text = parts.map(p => p.text).join(quote_joiner);
                quote_parts_target = 0; quote_parts = []; article_text.deselect();
                backend.prepare_quote(text); quote_dialog.open();
            }
            Rectangle {
                parent: Overlay.overlay
                objectName: "quoteSelectionPanel"
                visible: reader_scroll.quote_parts_target > 0
                anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter; anchors.topMargin: 8
                width: Math.min(700, parent.width - 24); height: quote_selection_controls.implicitHeight + 20
                color: p.panel; border.color: p.accent; radius: 10; z: 100
                ColumnLayout {
                    id: quote_selection_controls; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10; spacing: 6
                    Label { textFormat: Text.PlainText; text: "Cita · Parte " + (reader_scroll.quote_parts.length + 1) + " de " + reader_scroll.quote_parts_target + " · Arrastra para seleccionar el pasaje"; color: p.text; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    Label { textFormat: Text.PlainText; objectName: "quoteRemaining"; text: reader_scroll.quote_overlap ? "Selecciona un pasaje distinto, sin superponerlo al anterior." : (500 - reader_scroll.quote_used) + " caracteres disponibles de 500 (incluye […] entre partes)"; color: reader_scroll.quote_used > 500 || reader_scroll.quote_overlap ? p.danger : p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    Label { textFormat: Text.PlainText; visible: reader_scroll.quote_parts.length > 0; text: "Primera parte guardada. Puedes desplazarte hasta el segundo pasaje."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    RowLayout {
                        Action { objectName: "confirmQuotePart"; text: reader_scroll.quote_parts_target === 2 && reader_scroll.quote_parts.length === 0 ? "Guardar primera parte" : "Crear imagen"; enabled: !!reader_scroll.quote_selection && !reader_scroll.quote_overlap && reader_scroll.quote_used <= (reader_scroll.quote_parts_target === 2 && !reader_scroll.quote_parts.length ? 492 : 500); onClicked: reader_scroll.accept_quote_part() }
                        Action { text: "Cancelar"; onClicked: { reader_scroll.quote_parts_target = 0; reader_scroll.quote_parts = []; article_text.deselect(); } }
                    }
                }
            }

            ColumnLayout {
                id: reader_content
                width: window.reading_mode ? Math.min(960, reader_scroll.availableWidth) : reader_scroll.availableWidth
                x: (reader_scroll.availableWidth - width) / 2; spacing: 12
                RowLayout {
                    visible: !window.reading_mode; Layout.fillWidth: true; Layout.leftMargin: 16; Layout.rightMargin: 16; Layout.topMargin: 12
                    Action { objectName: "backToFeed"; text: "← Volver al feed"; onClicked: backend.close_article() }
                    RadarBadge { objectName: "readerRadarBadge"; article: s.reader; visible: s.radar; Layout.minimumWidth: 100 }
                    Item { Layout.fillWidth: true }
                }
                Image { objectName: "readerCover"; source: s.reader.image || ""; visible: s.reader.show_image && source.toString().length > 0; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; Layout.preferredHeight: visible ? Math.min(280,width*9/16) : 0; fillMode: Image.PreserveAspectCrop; clip: true; smooth: true; mipmap: true }
                Search { id: body_search; objectName: "body_search"; visible: !window.reading_mode; placeholderText: "Buscar en artículo"; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; onTextEdited: backend.search_document(text); onAccepted: backend.next_match() }
                RowLayout {
                    objectName: "readerToolbar"; visible: !window.reading_mode
                    Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; spacing: 8
                    Flow {
                        Layout.fillWidth: true; Layout.preferredHeight: childrenRect.height; spacing: 6
                        IconAction { kind: "archive"; stateActive: !!s.reader.archived; hint: s.reader.archived ? "Quitar de Archivados" : "Archivar artículo"; onClicked: backend.toggle_archived(s.reader.link) }
                        IconAction { kind: "save"; filled: !!s.reader.saved; hint: filled ? "Quitar guardado" : "Guardar"; onClicked: backend.toggle_saved(s.reader.link) }
                        IconAction { objectName: "readerDownload"; kind: s.reader.downloaded ? "delete" : "download"; filled: !!s.reader.downloaded; enabled: !s.reader.downloading; hint: filled ? "Eliminar descarga" : "Descargar"; onClicked: backend.toggle_download(s.reader.link) }
                        Action { objectName: "readerTranslate"; compact: true; text: s.reader.translating ? "Cancelar traducción" : s.reader.translated ? "Ver original" : "Leer en español"; active: true; enabled: s.reader.ready; onClicked: s.reader.translating ? backend.cancel_translation() : backend.translate_article() }
                    Action {
                        text: "Aa"; compact: true; objectName: "readerFontButton"
                        ToolTip.visible: hovered; ToolTip.text: "Tamaño de letra"
                        onClicked: font_menu.open()
                        Menu {
                            id: font_menu
                            Repeater {
                                model: [14, 16, 20, 24]
                                MenuItem {
                                    required property int modelData
                                    text: ["Pequeña", "Mediana", "Grande", "Muy grande"][[14,16,20,24].indexOf(modelData)]
                                    font.pixelSize: modelData
                                    checkable: true; checked: s.reader.font_size === modelData
                                    onTriggered: backend.set_reader_font_size(modelData, false)
                                }
                            }
                        }
                    }
                        Action { objectName: "enterReadingMode"; compact: true; text: "⛶ Modo lectura"; onClicked: window.enter_reading_mode() }
                        Action { objectName: "readerOpenOriginal"; compact: true; text: "Abrir original ↗"; onClicked: backend.open_url(s.reader.link) }
                    }
                    IconAction { objectName: "readerDismiss"; Layout.alignment: Qt.AlignRight | Qt.AlignBottom; kind: "dismiss"; stateActive: !!s.reader.dismissed; hint: s.reader.dismissed ? "Deshacer descarte" : "No me interesa · Volver al feed"; onClicked: backend.toggle_dismissed(s.reader.link) }
                }
                Action { text: "Colecciones"; visible: s.reader.saved && !window.reading_mode; compact: true; Layout.leftMargin: 18; onClicked: { article_collections.article_link=s.reader.link; article_collections.open(); } }
                Label { textFormat: Text.PlainText; text: "WEB · Publicación extraída del sitio"; visible: !!s.reader.web_extracted; color: p.accent; Layout.leftMargin: 22 }
                SectionTitle { text: s.reader.title || ""; font.pixelSize: 23; Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22 }
                Label { textFormat: Text.PlainText; visible: !window.reading_mode || reader_scroll.marking || !s.reader.ready; text: (reader_scroll.marking ? reader_scroll.erasing ? "Borrador activo · Haz clic o arrastra para quitar bloques destacados completos. " : "Destacador activo · Arrastra para pintar; repasar conserva el destacado. " : "") + (s.reader.status || ""); color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22 }
                TextEdit {
                    id: article_text; objectName: "article_text"; Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 66
                    Layout.bottomMargin: 28
                    Layout.preferredHeight: Math.max(contentHeight, images_bottom, notes_bottom)
                    property var note_layout: []
                    property real notes_bottom: note_layout.reduce((bottom, note) => Math.max(bottom, note.y + 38), 0)
                    property var notes: s.reader.notes || []
                    onNotesChanged: note_layout_timer.restart()
                    Timer { id: note_layout_timer; interval: 0; onTriggered: article_text.update_note_layout() }
                    function update_note_layout() {
                        let bottom = -38;
                        note_layout = notes.slice().sort((a,b) => a.position - b.position).map(note => {
                            const y = Math.max(positionToRectangle(note.position).y, bottom + 38);
                            bottom = y;
                            return {note: note, y: y};
                        });
                    }
                    property var image_entries: s.reader.inline_images || []
                    property var image_layout: []
                    property real images_bottom: image_layout.reduce((bottom, entry) => Math.max(bottom, entry.y + entry.height + 12), 0)
                    function update_image_layout() {
                        const next = backend.reader_image_layout(textDocument);
                        const unchanged = next.length === image_layout.length && next.every((entry, i) => {
                            const previous = image_layout[i];
                            return entry.y === previous.y && entry.x === previous.x
                                && entry.width === previous.width && entry.height === previous.height
                                && entry.position === previous.position
                                && entry.stack === previous.stack && entry.source === previous.source
                                && entry.alt === previous.alt;
                        });
                        if (!unchanged) image_layout = next;
                    }
                    // Coalesce changes and measure after Qt has reflowed the text.
                    onImage_entriesChanged: Qt.callLater(update_image_layout)
                    onContentHeightChanged: { Qt.callLater(update_image_layout); note_layout_timer.restart(); }
                    onWidthChanged: { Qt.callLater(update_image_layout); note_layout_timer.restart(); }
                    onFontChanged: { Qt.callLater(update_image_layout); note_layout_timer.restart(); }
                    Connections {
                        target: backend
                        function onDocument_layout_changed() { Qt.callLater(article_text.update_image_layout); note_layout_timer.restart(); }
                    }
                    text: s.reader.body || ""; textFormat: TextEdit.PlainText; readOnly: true; selectByMouse: !reader_scroll.marking; persistentSelection: true
                    wrapMode: TextEdit.Wrap; color: p.text; font.pixelSize: s.reader.font_size || 16; selectionColor: p.accent; selectedTextColor: p.accent_text
                    Repeater {
                        model: article_text.image_layout
                        delegate: Image {
                            objectName: "inlineArticleImage"
                            required property var modelData
                            x: modelData.x; y: modelData.y
                            width: modelData.width; height: modelData.height
                            source: modelData.source; fillMode: Image.PreserveAspectFit
                            asynchronous: true; smooth: true; mipmap: true
                            Accessible.name: modelData.alt || "Imagen del artículo"
                            z: 2
                            MouseArea {
                                anchors.fill: parent; cursorShape: Qt.PointingHandCursor; hoverEnabled: true
                                onClicked: image_viewer.show_image(parent.source, parent.Accessible.name)
                                ToolTip.visible: containsMouse; ToolTip.delay: 600
                                ToolTip.text: "Clic para ampliar"
                            }
                        }
                    }
                    Repeater {
                        model: article_text.note_layout
                        delegate: Rectangle {
                            required property var modelData
                            objectName: "articleNoteMarker"
                            x: article_text.width + 10; y: modelData.y
                            width: 32; height: 32; radius: 3; rotation: -3
                            color: modelData.note.color; border.color: Qt.darker(color, 1.2)
                            Rectangle { anchors.right: parent.right; anchors.bottom: parent.bottom; width: 8; height: 8; color: Qt.darker(parent.color, 1.15) }
                            Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: "≡"; color: "#443d30"; font.pixelSize: 23 }
                            MouseArea {
                                anchors.fill: parent; cursorShape: Qt.PointingHandCursor; hoverEnabled: true
                                onClicked: note_editor.show_note(parent.modelData.note)
                                ToolTip.visible: containsMouse; ToolTip.delay: 350
                                ToolTip.text: "<span>" + (parent.modelData.note.text.slice(0, 180) || "Abrir nota").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") + "</span>"
                            }
                            Accessible.name: "Abrir nota: " + modelData.note.text.slice(0, 80)
                        }
                    }
                    property string attached_text: ""
                    property string document_identity: (s.reader.link || "") + (s.reader.translated ? "|es" : "|original")
                    onDocument_identityChanged: { reader_scroll.quote_parts_target = 0; reader_scroll.quote_parts = []; Qt.callLater(function(){backend.attach_document(article_text.textDocument);}); }
                    onTextChanged: {
                        if (text !== attached_text) {
                            attached_text = text;
                            Qt.callLater(function(){backend.attach_document(article_text.textDocument); body_search.text="";});
                        }
                    }
                    Component.onCompleted: {
                        backend.attach_document(textDocument);
                        Qt.callLater(update_image_layout);
                    }
                    MouseArea {
                        objectName: "markerArea"
                        anchors.fill: parent; enabled: reader_scroll.marking; acceptedButtons: Qt.LeftButton; cursorShape: Qt.PointingHandCursor
                        preventStealing: true
                        property string gesture_identity: ""
                        property string gesture_text: ""
                        property string gesture_color: ""
                        property bool gesture_erasing: false
                        function preview(x, y) {
                            const end = article_text.positionAt(x, y);
                            article_text.select(Math.min(reader_scroll.mark_anchor, end), Math.max(reader_scroll.mark_anchor, end));
                        }
                        onPressed: function(mouse){
                            gesture_identity = article_text.document_identity;
                            gesture_text = article_text.text;
                            gesture_color = reader_scroll.marker_color;
                            gesture_erasing = reader_scroll.erasing;
                            reader_scroll.mark_anchor = article_text.positionAt(mouse.x,mouse.y);
                            article_text.deselect();
                        }
                        onPositionChanged: function(mouse){ if(pressed) preview(mouse.x, mouse.y); }
                        onReleased: function(mouse){
                            const end = article_text.positionAt(mouse.x,mouse.y);
                            article_text.deselect();
                            if (gesture_identity !== article_text.document_identity || gesture_text !== article_text.text) return;
                            if (gesture_erasing) backend.remove_marks(reader_scroll.mark_anchor, end);
                            else backend.mark(reader_scroll.mark_anchor, end, gesture_color);
                        }
                        onCanceled: article_text.deselect()
                    }
                    MouseArea {
                        anchors.fill: parent; acceptedButtons: Qt.RightButton
                        onClicked: function(mouse){reader_scroll.menu_position=article_text.positionAt(mouse.x,mouse.y);reader_scroll.selected_quote=article_text.selectedText;article_menu.popup();}
                    }
                    Menu {
                        id: article_menu; objectName: "readerContextMenu"
                        MenuItem {
                            objectName: "copyArticleText"
                            text: "Copiar texto"
                            enabled: article_text.selectionEnd > article_text.selectionStart
                            onTriggered: article_text.copy()
                        }
                        MenuSeparator {}
                        MenuItem { objectName: "createArticleNote"; text: "Añadir nota aquí…"; enabled: s.reader.ready; onTriggered: { const note = backend.create_note(reader_scroll.menu_position); if (note.id) note_editor.show_note(note); } }
                        MenuItem { text: "Guardar punto de lectura aquí"; onTriggered: backend.save_reading_position(reader_scroll.menu_position) }
                        MenuItem { objectName: "startSingleQuote"; text: "Crear cita: seleccionar un pasaje…"; enabled: s.reader.ready; onTriggered: reader_scroll.begin_quote(1) }
                        MenuItem { objectName: "startDoubleQuote"; text: "Crear cita: combinar dos pasajes…"; enabled: s.reader.ready; onTriggered: reader_scroll.begin_quote(2) }
                        Menu {
                            objectName: "markerMenu"; title: "Destacador"; width: Math.min(310, window.width - 40)
                            Repeater { model: s.marker_colors
                                delegate: MenuItem {
                                    id: marker_option
                                    required property var modelData
                                    objectName: "marker_" + modelData.name
                                    text: modelData.name
                                    contentItem: RowLayout {
                                        spacing: 8
                                        Rectangle { color: modelData.color; border.color: "#777777"; radius: 3; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
                                        Text { textFormat: Text.PlainText; text: modelData.name; color: marker_option.highlighted ? marker_option.palette.highlightedText : marker_option.palette.text; font.pixelSize: 13; Layout.fillWidth: true }
                                    }
                                    onTriggered: {
                                        reader_scroll.marker_color = modelData.color;
                                        reader_scroll.erasing = false;
                                        reader_scroll.marking = true;
                                        if (article_text.selectionEnd > article_text.selectionStart)
                                            backend.mark(article_text.selectionStart, article_text.selectionEnd, modelData.color);
                                        article_text.deselect();
                                    }
                                }
                            }
                            MenuItem { text: "Destacar selección"; enabled: article_text.selectionEnd > article_text.selectionStart; onTriggered: {backend.mark(article_text.selectionStart,article_text.selectionEnd,reader_scroll.marker_color);article_text.deselect();} }
                            MenuSeparator {}
                            MenuItem { objectName: "markerEraser"; text: "Borrador · bloques completos"; onTriggered: {reader_scroll.erasing=true;reader_scroll.marking=true;article_text.deselect();} }
                            MenuItem { text: "Desactivar destacador / borrador"; onTriggered: {reader_scroll.marking=false;reader_scroll.erasing=false;article_text.deselect();} }
                        }
                        MenuItem { text: article_text.selectionEnd > article_text.selectionStart ? "Quitar destacados completos de la selección" : "Quitar este destacado"; onTriggered: {if(article_text.selectionEnd>article_text.selectionStart)backend.remove_marks(article_text.selectionStart,article_text.selectionEnd);else backend.remove_mark_at(reader_scroll.menu_position);article_text.deselect();} }
                    }
                }
                Action {
                    objectName: "readerReadAction"; visible: !window.reading_mode
                    text: s.reader.seen ? "Marcar como no leído" : "Marcar como leído"
                    symbol: "read"; active: true
                    enabled: s.reader.ready
                    Layout.leftMargin: 22; Layout.rightMargin: 22; Layout.bottomMargin: 24
                    onClicked: backend.toggle_read(s.reader.link)
                }
            }
            Connections {
                target: backend
                function onDocument_search(position,count) {
                    if(position>=0){const r=article_text.positionToRectangle(position);reader_scroll.contentItem.contentY=Math.max(0,article_text.y+r.y-60);}
                    search_count.text = body_search.text.length ? count + " coincidencias" : "";
                }
            }
            Label { textFormat: Text.PlainText; id: search_count; visible: !window.reading_mode; color: p.muted; font.pixelSize: 10; anchors.right: parent.right; anchors.top: parent.top }
        }
    }

    Component {
        id: forest_page
        ColumnLayout {
            id: forest_review
            property string selected_url: ""
            property var rows: s.forest.rows
            property int current_index: Math.max(0, rows.findIndex(r => r.url === selected_url))
            property var current: rows.length ? rows[current_index] : null
            function move(delta) {
                if (rows.length) selected_url = rows[(current_index + delta + rows.length) % rows.length].url;
                forest_scroll.contentItem.contentY = 0;
            }
            function decide(action) {
                if (!current) return;
                const url = current.url;
                move(1);
                backend.forest_action(url, action);
            }
            function average(key) {
                return rows.length ? rows.reduce((sum,r) => sum + r[key], 0) / rows.length : 0;
            }
            spacing: 8
            RowLayout {
                Layout.fillWidth: true; Layout.margins: 10
                SectionTitle { text: "El Bosque · Cuida tus fuentes"; Layout.fillWidth: true }
                Action { objectName: "forestExit"; text: "Salir de El Bosque"; onClicked: backend.navigate("feed", "", "") }
            }
            Label { textFormat: Text.PlainText; text: "Revisa una fuente, compara su aporte y decide si quieres conservarla. " + s.forest.pending + " pendientes de revisión."; color: p.text; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18 }
            Label { textFormat: Text.PlainText; text: "Datos locales desde " + s.forest.started + ". Sin actividad registrada no significa falta de relevancia."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18 }
            RowLayout {
                Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                ComboBox {
                    objectName: "forestPeriod"
                    property var periods: ["", (new Date().getFullYear() + "-" + String(new Date().getMonth()+1).padStart(2,"0"))].concat(s.forest.months).filter((v,i,a) => a.indexOf(v) === i)
                    model: periods.map(v => v || "Histórico")
                    currentIndex: Math.max(0, periods.indexOf(s.forest_month))
                    onActivated: backend.forest_filter(periods[currentIndex], s.forest_sort)
                }
                ComboBox {
                    objectName: "forestSort"; Layout.preferredWidth: 240; Layout.maximumWidth: 240
                    property var keys: ["review", "received", "quiet", "opened", "highlighted", "quoted", "matched", "saved", "dismissed", "irrelevant", "unopened"]
                    model: ["Para revisar", "Más artículos recibidos", "Menos artículos recibidos", "Más abiertos", "Más destacados", "Más citas exportadas", "Más coincidencias Radar", "Más favoritos", "Más descartados", "Menor proporción Radar", "Menos abiertos"]
                    currentIndex: Math.max(0, keys.indexOf(s.forest_sort))
                    onActivated: backend.forest_filter(s.forest_month, keys[currentIndex])
                }
                Item { Layout.fillWidth: true }
            }
            RowLayout {
                Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                Action { objectName: "forestPrevious"; text: "‹ Anterior"; enabled: forest_review.rows.length > 1; onClicked: forest_review.move(-1) }
                Label { textFormat: Text.PlainText; text: forest_review.rows.length ? "Fuente " + (forest_review.current_index + 1) + " de " + forest_review.rows.length : "Sin fuentes"; color: p.muted; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
                Action { objectName: "forestNext"; text: "Siguiente ›"; enabled: forest_review.rows.length > 1; onClicked: forest_review.move(1) }
            }
            ScrollView {
                id: forest_scroll; objectName: "forestList"; Layout.fillWidth: true; Layout.fillHeight: true; Layout.margins: 10
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    width: forest_scroll.availableWidth; spacing: 14
                    Label { textFormat: Text.PlainText; visible: !forest_review.current; text: "Añade fuentes para empezar a cuidar tu Bosque."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    Rectangle {
                        visible: !!forest_review.current
                        Layout.fillWidth: true; implicitHeight: forest_card.implicitHeight + 24
                        color: p.card; border.color: p.border; radius: 10
                        ColumnLayout {
                            id: forest_card; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12; spacing: 8
                            property var entry: forest_review.current || ({name:"", url:"", review:"", reason:"", matched:0, evaluated:0, radar:"Sin evaluar"})
                            RowLayout {
                                Layout.fillWidth: true; spacing: 8
                                Image { objectName: "forestSourceIcon"; source: forest_card.entry.icon || ""; Layout.preferredWidth: 32; Layout.preferredHeight: 32; fillMode: Image.PreserveAspectFit; smooth: true
                                    Label { textFormat: Text.PlainText; anchors.centerIn: parent; visible: parent.status !== Image.Ready; text: (forest_card.entry.name || "?").charAt(0).toUpperCase(); color: p.accent; font.pixelSize: 24 }
                                }
                                Label { textFormat: Text.PlainText; objectName: "forestSourceName"; text: forest_card.entry.name; color: p.text; font.pixelSize: 22; font.bold: true; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            }
                            Label { textFormat: Text.PlainText; text: forest_card.entry.url; color: p.muted; elide: Text.ElideMiddle; Layout.fillWidth: true }
                            Label { textFormat: Text.PlainText; text: forest_card.entry.review; color: p.accent; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            Label { textFormat: Text.PlainText; text: "Esta fuente y el promedio de tus " + forest_review.rows.length + " fuentes"; color: p.text; font.bold: true; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            Label { textFormat: Text.PlainText; text: "Barra gruesa: esta fuente · Fina: promedio de todas, incluidos los ceros. Mismo período."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            GridLayout {
                                id: forest_metrics; objectName: "forestMetrics"
                                Layout.fillWidth: true; columns: width >= 700 ? 4 : width >= 540 ? 3 : 2
                                columnSpacing: 12; rowSpacing: 12
                                Repeater {
                                    model: [{key:"received",label:"Artículos recibidos"},{key:"opened",label:"Abiertos"},{key:"highlighted",label:"Destacados"},{key:"saved",label:"Favoritos"},{key:"quoted",label:"Citas exportadas"},{key:"matched",label:"Coincidencias Radar"},{key:"dismissed",label:"No me interesa"}]
                                    delegate: Rectangle {
                                        id: metric_card; required property var modelData
                                        Layout.fillWidth: true; Layout.preferredWidth: 1; implicitHeight: metric_content.implicitHeight + 16
                                        color: p.panel; radius: 8; border.color: p.border
                                        property real value: forest_card.entry[modelData.key] || 0
                                        property real mean: forest_review.average(modelData.key)
                                        property real maximum: Math.max(1, ...forest_review.rows.map(r => r[modelData.key]))
                                        property bool has_data: forest_review.rows.some(r => r[modelData.key] > 0)
                                        property int comparison: !has_data ? 0 : value > mean * 1.2 ? 1 : value < mean * 0.8 ? -1 : 0
                                        property int sentiment: modelData.key === "dismissed" ? -comparison : comparison
                                        property string assessment: !has_data ? "Sin actividad registrada para comparar" : comparison === 0 ? "Cerca del promedio (±20 %)" : (comparison > 0 ? "Por encima del promedio" : "Por debajo del promedio") + (modelData.key === "dismissed" ? " · Menos descartes es favorable" : " · Mayor actividad es favorable")
                                        ColumnLayout {
                                            id: metric_content; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 8; spacing: 3
                                            Label { textFormat: Text.PlainText; text: metric_card.modelData.label; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                            RowLayout {
                                                Layout.fillWidth: true
                                                Label { textFormat: Text.PlainText; text: metric_card.value; color: p.text; font.pixelSize: 22; font.bold: true; Layout.fillWidth: true }
                                                Label { textFormat: Text.PlainText;
                                                    objectName: "forestMood_" + metric_card.modelData.key
                                                    text: metric_card.sentiment > 0 ? "😄" : metric_card.sentiment < 0 ? "😴" : "😐"
                                                    font.pixelSize: 20; font.bold: true
                                                    padding: 5
                                                    horizontalAlignment: Text.AlignHCenter
                                                    background: Rectangle {
                                                        radius: 8
                                                        color: metric_card.sentiment > 0 ? (p.light ? "#e0f0e3" : "#243d2c") : metric_card.sentiment < 0 ? (p.light ? "#f8e3e1" : "#472c2c") : (p.light ? "#e1edf9" : "#25394d")
                                                        border.color: metric_card.sentiment > 0 ? (p.light ? "#75a981" : "#527c5f") : metric_card.sentiment < 0 ? (p.light ? "#d59b95" : "#97625d") : (p.light ? "#8ab0d4" : "#557b9f")
                                                    }
                                                    color: metric_card.sentiment > 0 ? (p.light ? "#397342" : "#8fc99b") : metric_card.sentiment < 0 ? (p.light ? "#a64545" : "#e4a09a") : p.muted
                                                    Accessible.name: metric_card.modelData.label + ": " + metric_card.assessment
                                                    HoverHandler { id: mood_hover }
                                                    ToolTip.visible: mood_hover.hovered
                                                    ToolTip.text: metric_card.assessment
                                                }
                                            }
                                            Label { textFormat: Text.PlainText; text: "Promedio: " + metric_card.mean.toFixed(1); color: p.muted }
                                            Rectangle { Layout.fillWidth: true; height: 7; radius: 3; color: p.hover
                                                Rectangle { width: parent.width * metric_card.value / metric_card.maximum; height: parent.height; radius: 3; color: p.accent }
                                            }
                                            Rectangle { Layout.fillWidth: true; height: 4; radius: 2; color: p.hover
                                                Rectangle { width: parent.width * metric_card.mean / metric_card.maximum; height: parent.height; radius: 2; color: p.muted }
                                            }
                                        }
                                    }
                                }
                            }
                            Label { textFormat: Text.PlainText; text: "Afinidad Radar: " + forest_card.entry.radar + " · " + forest_card.entry.matched + " de " + forest_card.entry.evaluated + " evaluados. Sin evaluar no equivale a cero coincidencias."; color: p.text; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            Label { textFormat: Text.PlainText; text: forest_card.entry.reason; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            Label { textFormat: Text.PlainText; text: "Recibidos: nuevos detectados. Cifras: artículos distintos. Citas: exportadas, no necesariamente compartidas."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }

                        }
                    }
                }
            }
            Flow {
                visible: !!forest_review.current; Layout.leftMargin: 18; Layout.rightMargin: 18
                                Layout.fillWidth: true; spacing: 6
                                Action { text: "Conservar y seguir"; onClicked: forest_review.decide("keep") }
                                Action { text: "Posponer 30 días"; onClicked: forest_review.decide("later") }
                                Action { text: "Ver artículos"; onClicked: backend.navigate("feed", "", forest_card.entry.url) }
                                Action { text: "Revisar ahora"; visible: !forest_card.entry.pending; onClicked: backend.forest_action(forest_card.entry.url, "reset") }
                                Action { text: "Eliminar fuente…"; warning: true; onClicked: { forest_delete.source_url = forest_card.entry.url; forest_delete.open(); } }
                            }
            Label { textFormat: Text.PlainText; visible: !!forest_review.current; Layout.leftMargin: 18; Layout.rightMargin: 18; text: "Conservar o posponer aplaza la revisión 30 días y pasa a la siguiente fuente. Seguirás recibiendo sus artículos."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
    }
    Dialog {
        id: forest_delete; objectName: "forestDeleteDialog"; anchors.centerIn: parent; modal: true
        title: "Eliminar fuente"; width: Math.min(480, window.width - 40)
        property string source_url: ""
        standardButtons: Dialog.Yes | Dialog.Cancel
        Label { textFormat: Text.PlainText; width: parent.width; text: "Se quitará esta fuente de todas sus categorías. Los artículos guardados y las estadísticas se conservan. ¿Continuar?"; color: p.text; wrapMode: Text.Wrap }
        onAccepted: backend.forest_action(source_url, "delete")
    }
    Component {
        id: about_page
        ScrollView {
            id: about_scroll; objectName: "aboutPage"; clip: true; contentWidth: availableWidth
            ColumnLayout {
                width: about_scroll.availableWidth; spacing: 12
                RowLayout {
                    Layout.fillWidth: true; Layout.margins: 18; spacing: 14
                    Image { source: s.logo; Layout.preferredWidth: 64; Layout.preferredHeight: 64; fillMode: Image.PreserveAspectFit }
                    ColumnLayout {
                        SectionTitle { text: s.about.name; font.pixelSize: 24 }
                        Label { textFormat: Text.PlainText; text: "Versión " + s.about.version + " · " + s.about.stage; color: p.accent }
                    }
                }
                Label { textFormat: Text.PlainText; text: s.about.description; color: p.text; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18 }
                Label { textFormat: Text.PlainText; text: "Autor: " + s.about.author + "\n" + s.about.location + " · GitHub: " + s.about.github; color: p.text; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18 }
                Label { textFormat: Text.PlainText; text: "Licencia de Choroy Reader: " + s.about.license; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18 }
                Flow {
                    Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; spacing: 6
                    Action { text: "Repositorio ↗"; active: true; onClicked: backend.open_url(s.about.repository) }
                    Action { text: "Reportar un error ↗"; active: true; onClicked: backend.open_url(s.about.issues) }
                }
                SectionTitle { text: "Actualizaciones"; Layout.leftMargin: 18 }
                Label { textFormat: Text.PlainText; objectName: "updateStatus"; text: s.updates.message; color: p.text; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18 }
                Flow {
                    Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; spacing: 6
                    Action { objectName: "checkUpdates"; text: s.updates.busy ? "Buscando…" : "Buscar actualizaciones"; enabled: !s.updates.busy; onClicked: backend.check_updates() }
                    Action { text: "Descargar nueva versión ↗"; visible: s.updates.available; onClicked: backend.open_url(s.updates.url) }
                }
                Label { textFormat: Text.PlainText; visible: s.updates.available; text: "Descarga el instalador desde la publicación. Cierra Choroy Reader e instala el nuevo paquete para actualizar conservando tu biblioteca."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18 }
                Label { textFormat: Text.PlainText; visible: s.updates.available && s.updates.notes.length > 0; text: s.updates.notes; color: p.text; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18 }
                SectionTitle { text: "Créditos"; Layout.leftMargin: 18 }
                Repeater {
                    model: s.about.credits
                    Label { textFormat: Text.PlainText; required property string modelData; text: modelData; color: p.text; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18 }
                }
                SectionTitle { text: "Dependencias y licencias"; Layout.leftMargin: 18 }
                Label { textFormat: Text.PlainText; text: "Avisos incluidos con esta versión. Pulsa una dependencia para leer los textos sin conexión."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18 }
                Repeater {
                    model: s.about.dependencies
                    delegate: Rectangle {
                        required property var modelData; required property int index
                        Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                        implicitHeight: dependency_row.implicitHeight + 12
                        radius: 8; color: p.panel; border.color: p.border
                        RowLayout {
                            id: dependency_row; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 6
                            Action { text: modelData.name + " · " + modelData.version + "\n" + modelData.license; Layout.fillWidth: true; onClicked: { backend.show_dependency_license(index); license_dialog.open(); } }
                            Action { text: "↗"; visible: modelData.url.length > 0; Accessible.name: "Sitio de " + modelData.name; onClicked: backend.open_url(modelData.url) }
                        }
                    }
                }
                Item { Layout.preferredHeight: 18 }
            }
        }
    }
    Component {
        id: storage_page
        ScrollView {
            id: storage_scroll; objectName: "storagePage"; clip: true; contentWidth: availableWidth
            ColumnLayout {
                width: storage_scroll.availableWidth; spacing: 14
                SectionTitle { text: "Almacenamiento"; Layout.margins: 18 }
                Label { textFormat: Text.PlainText;
                    text: "Revisa qué ocupa espacio en Choroy Reader y libera solo archivos que la aplicación puede recrear.";
                    color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                }
                Rectangle {
                    Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                    implicitHeight: storage_totals.implicitHeight + 24; radius: 10; color: p.panel; border.color: p.border
                    ColumnLayout {
                        id: storage_totals; anchors.fill: parent; anchors.margins: 12; spacing: 4
                        Label { textFormat: Text.PlainText; text: "Datos del usuario"; color: p.muted; font.pixelSize: 11 }
                        Label { textFormat: Text.PlainText; text: s.storage.user_total; color: p.accent; font.pixelSize: 24; font.bold: true }
                        Label { textFormat: Text.PlainText; text: s.storage.data_path; color: p.text; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true }
                        Label { textFormat: Text.PlainText; text: s.storage.installation_shared ? "Esta ejecución comparte carpeta con sus datos; por eso no se suma una instalación separada." : "Los archivos de instalación se conservan aparte: " + s.storage.installation_total; color: p.muted; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    }
                }
                SectionTitle { text: "Uso de datos"; Layout.leftMargin: 18 }
                Repeater {
                    model: [
                        { name: "Base de datos", value: s.storage.database, detail: "Estado de lectura, progreso y destacados." },
                        { name: "Artículos", value: s.storage.articles, detail: "Feed, guardados, descargas, historial y archivados." },
                        { name: "Imágenes", value: s.storage.images, detail: "Portadas generadas para mostrar en la aplicación." },
                        { name: "Caché", value: s.storage.cache, detail: "Favicons y archivos temporales regenerables." },
                        { name: "Otros datos", value: s.storage.other, detail: "Configuración y archivos de usuario restantes." }
                    ]
                    delegate: Rectangle {
                        required property var modelData
                        Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                        implicitHeight: storage_row.implicitHeight + 18; radius: 8; color: p.panel; border.color: p.border
                        RowLayout {
                            id: storage_row; anchors.fill: parent; anchors.margins: 9; spacing: 10
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 2
                                Label { textFormat: Text.PlainText; text: modelData.name; color: p.text; font.bold: true }
                                Label { textFormat: Text.PlainText; text: modelData.detail; color: p.muted; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            }
                            Label { textFormat: Text.PlainText; text: modelData.value; color: p.accent; font.bold: true; Layout.alignment: Qt.AlignRight | Qt.AlignVCenter }
                        }
                    }
                }
                SectionTitle { text: "Limpieza segura"; Layout.leftMargin: 18; Layout.topMargin: 4 }
                Label { textFormat: Text.PlainText;
                    text: s.storage.recoverable_bytes > 0 ? "Puedes recuperar aproximadamente " + s.storage.recoverable + ". Se conservarán tus fuentes, configuración, artículos, descargas y base de datos." : "No hay caché regenerable para limpiar.";
                    color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                }
                RowLayout {
                    Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; spacing: 8
                    Action { text: "Actualizar tamaños"; Layout.fillWidth: true; onClicked: backend.refresh_storage() }
                    Action { text: "Limpiar caché (" + s.storage.recoverable + ")"; active: true; enabled: s.storage.recoverable_bytes > 0; Layout.fillWidth: true; onClicked: clear_cache_dialog.open() }
                }
                Label { textFormat: Text.PlainText; text: (s.storage.installation_shared ? "Carpeta compartida: " : "Instalación: ") + s.storage.installation_path; color: p.muted; font.pixelSize: 10; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18 }
                Item { Layout.preferredHeight: 18 }
            }
        }
    }
    Dialog {
        id: clear_cache_dialog; objectName: "clearCacheDialog"; anchors.centerIn: parent; modal: true
        width: Math.min(520, window.width - 40); title: "Limpiar caché"
        background: Rectangle { color: p.panel; radius: 10; border.color: p.border }
        contentItem: Label { textFormat: Text.PlainText;
            text: "Se eliminarán " + s.storage.recoverable + " de imágenes, favicons y archivos temporales que Choroy Reader puede descargar o generar de nuevo. Tus artículos, descargas, fuentes y configuración no se modificarán.";
            color: p.text; wrapMode: Text.Wrap; padding: 18
        }
        footer: RowLayout {
            Item { Layout.fillWidth: true }
            Action { text: "Cancelar"; onClicked: clear_cache_dialog.close() }
            Action { text: "Limpiar caché"; active: true; onClicked: { backend.clear_storage_cache(); clear_cache_dialog.close(); } }
            Item { width: 8 }
        }
    }
    Dialog {
        id: license_dialog; objectName: "licenseDialog"; anchors.centerIn: parent; modal: true
        width: Math.min(760, window.width - 40); height: Math.min(580, window.height - 40)
        title: s.notice_title
        background: Rectangle { color: p.panel; radius: 10; border.color: p.border }
        header: Label { textFormat: Text.PlainText; text: license_dialog.title; color: p.text; font.bold: true; padding: 16 }
        contentItem: ScrollView {
            id: license_scroll; clip: true; contentWidth: availableWidth
            TextArea { width: license_scroll.availableWidth; text: s.notice_body; textFormat: TextEdit.PlainText; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; color: p.text; selectionColor: p.accent; selectedTextColor: p.accent_text; background: Item {} }
        }
        footer: Action { text: "Cerrar"; onClicked: license_dialog.close() }
    }

    Component {
        id: design_page
        ScrollView { id: design_scroll; clip: true; contentWidth: availableWidth
            ColumnLayout { width: design_scroll.availableWidth; spacing: 16
                SectionTitle { text: "Diseño"; Layout.margins: 18 }
                RowLayout { Layout.leftMargin: 18
                    Label { textFormat: Text.PlainText; text: "Tamaño de letra predeterminado"; color: p.text }
                    ComboBox {
                        objectName: "defaultReaderFontSize"
                        model: ["Pequeña · 14", "Mediana · 16", "Grande · 20", "Muy grande · 24"]
                        currentIndex: [14,16,20,24].indexOf(s.default_font_size)
                        onActivated: backend.set_reader_font_size([14,16,20,24][currentIndex], true)
                    }
                }
                Check { text: "Mostrar imágenes dentro de los artículos"; checked: s.show_images; Layout.leftMargin: 18; onClicked: backend.set_design(s.columns,checked,s.translate_titles) }
                Check { text: "Mostrar traducción de los títulos"; checked: s.translate_titles; Layout.leftMargin: 18; onClicked: backend.set_design(s.columns,s.show_images,checked) }
                RowLayout { Layout.leftMargin: 18
                    Label { textFormat: Text.PlainText; text: "Artículos por fila (máximo)"; color: p.text }
                    SpinBox { from: 1; to: 5; value: s.columns; onValueModified: backend.set_design(value,s.show_images,s.translate_titles) }
                }
                SectionTitle { text: "Tema"; Layout.leftMargin: 18 }
                Flow { Layout.fillWidth: true; Layout.margins: 18; spacing: 8
                    Repeater { model: s.themes
                        delegate: Button { required property var modelData; text: modelData.name; onClicked: backend.set_theme(modelData.key); padding: 12
                            background: Rectangle { radius: 6; color: modelData.key === "periodico" ? "#e6e6e6" : "#232323"; border.width: s.theme === modelData.key ? 2 : 1; border.color: modelData.color }
                            contentItem: Text { textFormat: Text.PlainText; text: parent.text; color: modelData.color }
                        }
                    }
                }
                Label { textFormat: Text.PlainText; text: "Las fuentes se actualizan al iniciar y al pulsar Actualizar feed."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.margins: 18 }
            }
        }
    }
    Component {
        id: radar_page
        ScrollView { id: radar_scroll; clip: true; contentWidth: availableWidth
            ColumnLayout { width: radar_scroll.availableWidth; spacing: 14
                SectionTitle { text: "Radar de intereses"; Layout.margins: 18 }
                Label { textFormat: Text.PlainText; text: "El radar busca tus intereses en los títulos y el contenido, y coloca primero los artículos más relevantes. Actívalo desde la barra lateral.\n\n◎ Un interés · ◎◎ Dos · ◎◎◎ Tres o más"; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18 }
                Check {
                    objectName: "radarBilingualToggle"
                    text: "Buscar también en inglés y español"; checked: s.radar_bilingual
                    Layout.leftMargin: 18; Layout.rightMargin: 18; Layout.alignment: Qt.AlignLeft
                    Layout.maximumWidth: radar_scroll.availableWidth - 36
                    onClicked: backend.set_radar_bilingual(checked)
                }
                Label { textFormat: Text.PlainText;
                    visible: s.radar_bilingual
                    text: s.radar_translating ? "Buscando equivalencias…" : "Las equivalencias aparecen junto a cada interés. Pulsa una etiqueta para editarlas."
                    color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                }
                RowLayout { Layout.fillWidth: true; Layout.margins: 18
                    Search { id: radar_input; placeholderText: "Escribe una palabra o frase y pulsa Enter"; Layout.fillWidth: true
                        function add_interest() { backend.add_radar_word(text); text=""; forceActiveFocus(); }
                        onAccepted: add_interest()
                    }
                    Action { text: "Agregar"; active: true; enabled: radar_input.text.trim().length > 0; onClicked: radar_input.add_interest() }
                }
                Flow {
                    id: radar_tags; objectName: "radarTags"
                    Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; spacing: 8
                    property var tags: {
                        const result = [];
                        for (const word of s.radar_words) {
                            result.push({word: word, label: word, equivalent: false});
                            if (s.radar_bilingual) {
                                for (const value of (s.radar_equivalents[word] || []))
                                    result.push({word: word, label: value, equivalent: true});
                            }
                        }
                        return result;
                    }
                    Repeater {
                        model: radar_tags.tags
                        delegate: Rectangle {
                            id: radar_tag; required property var modelData
                            objectName: "radarTag"
                            width: Math.min(tag_row.implicitWidth + 16, radar_tags.width)
                            height: 36; radius: 18; color: p.hover
                            border.color: modelData.equivalent ? p.accent : p.border
                            RowLayout {
                                id: tag_row; anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8; spacing: 2
                                Button {
                                    Layout.fillWidth: true; padding: 4
                                    text: radar_tag.modelData.label
                                    background: Item {}
                                    contentItem: Text { textFormat: Text.PlainText; text: parent.text; color: p.text; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
                                    onClicked: {
                                        equivalents_dialog.word = radar_tag.modelData.word;
                                        equivalents_edit.text = (s.radar_equivalents[equivalents_dialog.word] || []).join(", ");
                                        equivalents_dialog.open();
                                    }
                                }
                                Action {
                                    text: "×"; compact: true
                                    Accessible.name: "Eliminar " + radar_tag.modelData.label
                                    onClicked: {
                                        if (radar_tag.modelData.equivalent)
                                            backend.save_radar_equivalents(radar_tag.modelData.word,
                                                (s.radar_equivalents[radar_tag.modelData.word] || []).filter(value => value !== radar_tag.modelData.label).join(", "));
                                        else backend.remove_radar_word(radar_tag.modelData.word);
                                    }
                                }
                            }
                        }
                    }
                }
                Label { textFormat: Text.PlainText; visible: s.radar_words.length === 0; text: "Agrega tu primer interés para empezar."; color: p.muted; Layout.margins: 18 }
            }
        }
    }

    Dialog {
        id: equivalents_dialog; anchors.centerIn: parent; modal: true
        property string word: ""
        title: "Equivalencias de " + word
        width: Math.min(460, window.width - 40)
        background: Rectangle { color: p.panel; radius: 10; border.color: p.border }
        contentItem: ColumnLayout {
            Search { id: equivalents_edit; Layout.fillWidth: true; placeholderText: "Variantes separadas por comas" }
            RowLayout {
                Action { text: "Cancelar"; onClicked: equivalents_dialog.close() }
                Action { text: "Guardar"; onClicked: { backend.save_radar_equivalents(equivalents_dialog.word, equivalents_edit.text); equivalents_dialog.close(); } }
            }
        }
    }

    Component {
        id: sources_page
        ScrollView { id: sources_scroll; clip: true; contentWidth: availableWidth
            ColumnLayout { width: sources_scroll.availableWidth; spacing: 10
                RowLayout { Layout.fillWidth: true; Layout.margins: 18
                    SectionTitle { text: "Fuentes y categorías"; Layout.fillWidth: true }
                    Action { text: "+ Categoría"; active: true; onClicked: {category_dialog.edit(null);} }
                }
                RowLayout {
                    Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; spacing: 24
                    ColumnLayout {
                        Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.alignment: Qt.AlignTop; spacing: 8
                        Label { textFormat: Text.PlainText; text: "Mostrar artículos de"; color: p.text }
                        SettingsChoice {
                            id: period_selector; objectName: "articlePeriodSelector"
                            property var keys: ["hoy", "dos_dias", "semana", "mes", "ano"]
                            model: ["Hoy", "Últimos 2 días", "Últimos 7 días", "Últimos 30 días", "Este año"]
                            currentIndex: keys.indexOf(s.article_period)
                            onActivated: backend.set_article_period(keys[currentIndex])
                            Layout.fillWidth: true; Layout.maximumWidth: 220
                        }
                        Label { textFormat: Text.PlainText; text: "Se aplica a todas las fuentes. Actualiza el feed para aplicar el período; requiere fecha en el RSS. Guardados, archivados y descargas se conservan."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.alignment: Qt.AlignTop; spacing: 8
                        Label { textFormat: Text.PlainText; text: "Conservar historial"; color: p.text }
                        SettingsChoice {
                            objectName: "historyRetentionSelector"
                            property var days: [0, 1, 7, 30, 90, 180, 365]
                            model: ["Sin límite", "1 día", "1 semana", "30 días", "90 días", "180 días", "1 año"]
                            currentIndex: days.indexOf(s.history_days)
                            onActivated: backend.set_history_retention(days[currentIndex])
                            Layout.fillWidth: true; Layout.maximumWidth: 220
                        }
                        Label { textFormat: Text.PlainText; text: "Desde la primera recepción. Se protegen pendientes, guardados, archivados y descargas. La limpieza ocurre al iniciar y actualizar; puedes recuperar retirados durante 30 días. Se mantienen los estados de lectura y descarte."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    }
                }
                Action { text: "Recuperar historial retirado…"; Layout.leftMargin: 18; onClicked: backend.navigate("retirados", "", "") }
                Rectangle {
                    Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                    implicitHeight: portability_controls.implicitHeight + 24
                    radius: 8; color: p.panel; border.color: p.border
                    ColumnLayout {
                        id: portability_controls; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12; spacing: 8
                        SectionTitle { text: "Respaldo y portabilidad" }
                        Label { textFormat: Text.PlainText; text: "OPML intercambia fuentes y categorías. La copia local incluye preferencias, estados, colecciones, textos, destacados y progreso de lectura."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
                        Flow {
                            Layout.fillWidth: true; spacing: 6; enabled: s.portability_ready
                            Action { text: "Importar OPML…"; onClicked: opml_import_file.open() }
                            Action { text: "Exportar OPML…"; onClicked: opml_export_file.open() }
                            Action { text: "Crear copia…"; onClicked: backup_export_file.open() }
                            Action { text: "Restaurar copia…"; onClicked: backup_import_file.open() }
                        }
                        Label { textFormat: Text.PlainText; visible: !s.portability_ready; text: "Espera a que finalicen las tareas en curso."; color: p.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    }
                }
                Search { objectName: "sourceSearch"; placeholderText: "Buscar fuente por nombre, web o RSS"; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; text: window.management_query; onTextEdited: window.management_query = text }
                Label { textFormat: Text.PlainText; visible: window.management_query.length > 0 && !s.categories.some(cat => cat.sources.some(src => window.source_matches(src))); text: "No se encontraron fuentes"; color: p.muted; Layout.leftMargin: 18 }
                Repeater { model: s.categories
                    delegate: Rectangle {
                        id: settings_cat; objectName: "managed_" + modelData.name; required property var modelData
                        property bool expanded: window.management_query.trim().length > 0 || !!window.managed_categories[modelData.name]
                        visible: !window.management_query.trim().length || modelData.sources.some(src => window.source_matches(src))
                        function reveal_target() { if (window.management_target === modelData.name) Qt.callLater(() => { const point = settings_cat.mapToItem(sources_scroll.contentItem.contentItem, 0, 0); sources_scroll.contentItem.contentY = Math.max(0, Math.min(point.y, sources_scroll.contentItem.contentHeight - sources_scroll.availableHeight)); window.management_target = ""; }); }
                        Component.onCompleted: reveal_target()
                        Connections { target: window; function onManagement_targetChanged() { settings_cat.reveal_target(); } }
                         Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; implicitHeight: cat_settings.implicitHeight+20; color: p.panel; border.color: p.border; radius: 6
                        ColumnLayout { id: cat_settings; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10; spacing: 6
                            RowLayout { Layout.fillWidth: true
                                Action { text: (settings_cat.expanded ? "⌄  " : "›  ") + settings_cat.modelData.name + " · " + settings_cat.modelData.sources.length; favicon: settings_cat.modelData.icon; Layout.fillWidth: true; onClicked: { const next = Object.assign({}, window.managed_categories); next[settings_cat.modelData.name] = !settings_cat.expanded; window.managed_categories = next; } }
                                Action { text: "↑"; compact: true; onClicked: backend.move_category(settings_cat.modelData.index,-1) }
                                Action { text: "↓"; compact: true; onClicked: backend.move_category(settings_cat.modelData.index,1) }
                                Action { text: "Editar"; compact: true; onClicked: {category_dialog.edit(settings_cat.modelData);} }
                                Action { text: "×"; compact: true; onClicked: backend.delete_category(settings_cat.modelData.index) }
                            }
                            Repeater { model: settings_cat.expanded ? settings_cat.modelData.sources.filter(src => window.source_matches(src)) : []
                                delegate: ColumnLayout { id: source_row; required property var modelData; Layout.fillWidth: true
                                    RowLayout { Layout.fillWidth: true
                                        Image { source: source_row.modelData.icon; visible: source.toString().length>0; Layout.preferredWidth: 16; Layout.preferredHeight: 16; smooth: true; mipmap: true }
                                        Label { textFormat: Text.PlainText; text: source_row.modelData.name; color: p.text; Layout.fillWidth: true; wrapMode: Text.Wrap }
                                        Action { text: "Editar"; compact: true; onClicked: source_dialog.edit(settings_cat.modelData.index,source_row.modelData) }
                                        Action { text: "↑"; compact: true; onClicked: backend.move_source(settings_cat.modelData.index,source_row.modelData.index,-1) }
                                        Action { text: "↓"; compact: true; onClicked: backend.move_source(settings_cat.modelData.index,source_row.modelData.index,1) }
                                        Action { text: "×"; compact: true; onClicked: {delete_dialog.cat=settings_cat.modelData.index;delete_dialog.src=source_row.modelData.index;delete_dialog.open();} }
                                    }
                                    Label { textFormat: Text.PlainText; text: source_row.modelData.feed || source_row.modelData.url; color: p.muted; font.pixelSize: 10; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                }
                            }
                            Action { visible: settings_cat.expanded; text: "+ Añadir fuente"; active: true; onClicked: source_dialog.edit(settings_cat.modelData.index,null) }
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: bulk_dialog; objectName: "offline_dialog"; anchors.centerIn: parent; modal: true; title: "Preparar lectura sin conexión"
        width: Math.min(460, window.width-40)
        background: Rectangle { color: p.panel; radius: 10; border.color: p.border }
        contentItem: ColumnLayout {
            spacing: 14
            Label { textFormat: Text.PlainText; text: "Descarga todos los artículos cargados en el feed, con su texto e imagen. Las descargas existentes se conservan."; color: p.text; wrapMode: Text.Wrap; Layout.fillWidth: true }
            Check { id: offline_translation; text: "Incluir traducción al español"; Layout.fillWidth: true }
            Label { textFormat: Text.PlainText; text: "Preparar las traducciones requiere conexión y puede tardar. Después podrás leerlas sin internet."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
            RowLayout { Action { text: "Cancelar"; onClicked: bulk_dialog.close() } Action { text: "Modo offline"; active: true; onClicked: {backend.download_all(offline_translation.checked);bulk_dialog.close();} } }
        }
    }
    Dialog {
        id: category_dialog
        property string icon_url: ""
        function edit(cat) { category_index = cat ? cat.index : -1; category_name.text = cat ? cat.name : ""; icon_url = cat ? cat.icon : ""; open(); }
        property int category_index: -1; anchors.centerIn: parent; modal: true; title: category_index<0 ? "Nueva categoría" : "Editar categoría"; width: Math.min(400,window.width-40)
        background: Rectangle { color: p.panel; radius: 10; border.color: p.border }
        contentItem: ColumnLayout {
            Search { id: category_name; placeholderText: "Nombre"; Layout.fillWidth: true }
            RowLayout {
                Image { source: category_dialog.icon_url; visible: source.toString().length > 0; Layout.preferredWidth: 24; Layout.preferredHeight: 24; fillMode: Image.PreserveAspectFit }
                Action { text: "Elegir icono…"; onClicked: category_icon_file.open() }
                Action { text: "Quitar icono"; onClicked: category_dialog.icon_url = "" }
            }
            RowLayout { Action { text: "Cancelar"; onClicked: category_dialog.close() } Action { text: "Guardar"; active: true; onClicked: {backend.save_category(category_dialog.category_index,category_name.text,category_dialog.icon_url);category_dialog.close();} } }
        }
    }
    Dialog {
        id: collection_dialog; anchors.centerIn: parent; modal: true; title: "Nueva colección"; width: Math.min(400,window.width-40)
        background: Rectangle { color: p.panel; radius: 10; border.color: p.border }
        contentItem: ColumnLayout {
            spacing: 12
            Label { textFormat: Text.PlainText; text: "Las colecciones organizan tus artículos guardados y no modifican las categorías de fuentes."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
            Search { id: collection_name; placeholderText: "Nombre de la colección"; Layout.fillWidth: true; onAccepted: { backend.save_collection(text); collection_dialog.close(); } }
            RowLayout { Item { Layout.fillWidth: true } Action { text: "Cancelar"; onClicked: collection_dialog.close() } Action { text: "Crear"; active: true; onClicked: { backend.save_collection(collection_name.text); collection_dialog.close(); } } }
        }
    }
    Dialog {
        id: article_collections; property string article_link: ""; anchors.centerIn: parent; modal: true; title: "Organizar en colecciones"; width: Math.min(440,window.width-40)
        background: Rectangle { color: p.panel; radius: 10; border.color: p.border }
        contentItem: ColumnLayout {
            spacing: 8
            Label { textFormat: Text.PlainText; text: "Un artículo puede pertenecer a varias colecciones."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
            Repeater { model: s.collections.slice(1)
                delegate: Check {
                    required property var modelData
                    text: modelData.name; Layout.fillWidth: true
                    checked: s.reader.collections.indexOf(modelData.name) >= 0
                    onClicked: backend.toggle_article_collection(article_collections.article_link, modelData.id)
                }
            }
            Label { textFormat: Text.PlainText; visible: s.collections.length <= 1; text: "Aún no hay colecciones. Créala desde Guardados."; color: p.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
            RowLayout { Item { Layout.fillWidth: true } Action { text: "Cerrar"; onClicked: article_collections.close() } }
        }
    }
    Dialog {
        id: delete_dialog; property int cat: -1; property int src: -1; anchors.centerIn: parent; modal: true; title: "¿Eliminar esta fuente?"
        standardButtons: Dialog.Yes | Dialog.Cancel; onAccepted: backend.delete_source(cat,src)
    }
    Dialog {
        id: source_dialog; objectName: "source_editor"; anchors.centerIn: parent; modal: true; width: Math.min(520,window.width-40); height: Math.min(640,window.height-40); title: "Fuente"
        property int category_index: -1; property int source_index: -1; property string icon_url: ""
        function edit(ci,src) { category_index=ci;source_index=src?src.index:-1;src_name.text=src?src.name:"";src_url.text=src?src.url:"";src_feed.text=src?src.feed:"";src_maximum.value=src?src.maximum:100;src_translation.checked=src?src.translate:true;src_shortcut.checked=src?src.shortcut:false;src_show_shortcut.checked=src?src.show_shortcut:false;src_category.currentIndex=ci;icon_url=src?src.icon:"";open(); }
        background: Rectangle { color: p.panel; radius: 10; border.color: p.border }
        header: Label { textFormat: Text.PlainText; text: source_dialog.title; color: p.text; padding: 16; font.bold: true }
        contentItem: ScrollView { id: source_editor_scroll; clip: true; contentWidth: availableWidth
            ColumnLayout { width: source_editor_scroll.availableWidth; spacing: 12
                Search { id: src_name; placeholderText: "Nombre de la fuente"; Layout.fillWidth: true }
                Search { id: src_url; placeholderText: "https://sitio.com"; Layout.fillWidth: true }
                Check { id: src_show_shortcut; text: "Mostrar atajo en la barra superior"; Layout.fillWidth: true }
                Check { id: src_shortcut; text: "Solo sitio web (sin cargar artículos)"; Layout.fillWidth: true }
                Search { visible: !src_shortcut.checked; id: src_feed; placeholderText: "URL RSS (opcional, se detecta al actualizar)"; Layout.fillWidth: true }
                Label { textFormat: Text.PlainText; visible: !src_shortcut.checked; text: "Sin RSS, se intentarán extraer las publicaciones de esta página. Usa la dirección del blog o sección de noticias. Se identificarán con la etiqueta WEB."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
                ComboBox { id: src_category; model: s.categories; textRole: "name"; Layout.fillWidth: true; implicitHeight: 38
                    background: Rectangle { radius: 8; color: p.hover; border.color: src_category.activeFocus ? p.accent : p.border }
                    contentItem: Text { textFormat: Text.PlainText; text: src_category.displayText; color: p.text; leftPadding: 12; rightPadding: 28; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
                    indicator: Text { textFormat: Text.PlainText; text: "⌄"; color: p.muted; x: parent.width-width-12; y: (parent.height-height)/2 }
                    delegate: ItemDelegate { required property var modelData; width: src_category.width; text: modelData.name
                        contentItem: Text { textFormat: Text.PlainText; text: parent.text; color: p.text; padding: 8 }
                        background: Rectangle { color: parent.hovered ? p.hover : p.panel }
                    }
                    popup: Popup { y: src_category.height+4; width: src_category.width; implicitHeight: Math.min(240, category_choices.contentHeight+8); padding: 4
                        background: Rectangle { color: p.panel; radius: 8; border.color: p.border }
                        contentItem: ListView { id: category_choices; clip: true; model: src_category.popup.visible ? src_category.delegateModel : null; currentIndex: src_category.highlightedIndex }
                    }
                }
                RowLayout { visible: !src_shortcut.checked; Label { textFormat: Text.PlainText; text: "Límite por fuente"; color:p.text } SpinBox { id: src_maximum; from:1; to:1000; implicitWidth: 150; implicitHeight: 38
                    background: Rectangle { color: p.hover; radius: 8; border.color: src_maximum.activeFocus ? p.accent : p.border }
                    contentItem: Text { textFormat: Text.PlainText; text: src_maximum.value; color: p.text; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    down.indicator: Rectangle { x: 0; width: 36; height: parent.height; radius: 8; color: src_maximum.down.hovered ? p.border : p.hover; Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: "−"; color: p.text; font.pixelSize: 20 } }
                    up.indicator: Rectangle { x: parent.width-width; width: 36; height: parent.height; radius: 8; color: src_maximum.up.hovered ? p.border : p.hover; Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: "+"; color: p.text; font.pixelSize: 20 } }
                } }
                Switch { visible: !src_shortcut.checked; id: src_translation; text: "Traducir títulos al español"; Layout.fillWidth: true; padding: 10; spacing: 12
                    background: Rectangle { radius: 8; color: p.hover; border.color: src_translation.hovered ? p.accent : p.border }
                    indicator: Rectangle { x: 10; y: (src_translation.height-height)/2; width: 42; height: 24; radius: 12; color: src_translation.checked ? ((s.theme === "gris" || s.theme === "periodico") ? "#62834b" : p.accent) : "#777b82"
                        Rectangle { x: src_translation.checked ? 21 : 3; y: 3; width: 18; height: 18; radius: 9; color: "#ffffff"; Behavior on x { NumberAnimation { duration: 110 } } }
                    }
                    contentItem: Text { textFormat: Text.PlainText; text: src_translation.text; color: p.text; leftPadding: 54; verticalAlignment: Text.AlignVCenter }
                }
                RowLayout { Action { text: "Elegir icono"; onClicked: icon_file.open() } Action { text: "Quitar icono"; onClicked: source_dialog.icon_url="" } }
                RowLayout { Action { text: "Cancelar"; onClicked: source_dialog.close() } Action { text: "Guardar"; active:true; onClicked: {if (backend.save_source(source_dialog.category_index,source_dialog.source_index,src_category.currentIndex,src_name.text,src_url.text,src_feed.text,src_maximum.value,src_translation.checked,source_dialog.icon_url,src_shortcut.checked,src_show_shortcut.checked)) source_dialog.close();} } }
            }
        }
    }
    Dialog {
        id: image_viewer; objectName: "articleImageViewer"
        anchors.centerIn: parent; width: window.width - 40; height: window.height - 40
        modal: true; focus: true; padding: 12
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        property url image_source: ""
        property string image_description: ""
        property real zoom: 1
        function show_image(source, description) {
            image_source = source; image_description = description; zoom = 1;
            image_pan.contentX = 0; image_pan.contentY = 0;
            open();
        }
        onClosed: image_source = ""
        background: Rectangle { color: p.bg; border.color: p.border; radius: 10 }
        header: RowLayout {
            spacing: 8
            Label { textFormat: Text.PlainText; text: image_viewer.image_description || "Imagen del artículo"; color: p.text; elide: Text.ElideRight; Layout.fillWidth: true; Layout.margins: 12 }
            Action { text: "−"; enabled: image_viewer.zoom > 1; onClicked: image_viewer.zoom = Math.max(1, image_viewer.zoom / 1.5); Accessible.name: "Reducir imagen" }
            Action { text: "Ajustar"; onClicked: { image_viewer.zoom = 1; image_pan.contentX = 0; image_pan.contentY = 0; } }
            Action { text: "+"; objectName: "enlargeArticleImage"; enabled: image_viewer.zoom < 4; onClicked: image_viewer.zoom = Math.min(4, image_viewer.zoom * 1.5); Accessible.name: "Ampliar imagen" }
            Action { text: "Cerrar ×"; objectName: "closeArticleImage"; Layout.rightMargin: 12; onClicked: image_viewer.close() }
        }
        contentItem: Flickable {
            id: image_pan; clip: true; boundsBehavior: Flickable.StopAtBounds
            contentWidth: Math.max(width, enlarged_image.width)
            contentHeight: Math.max(height, enlarged_image.height)
            ScrollBar.horizontal: ScrollBar {}
            ScrollBar.vertical: ScrollBar {}
            Image {
                id: enlarged_image; objectName: "enlargedArticleImage"
                anchors.centerIn: parent; source: image_viewer.image_source
                property real ratio: implicitWidth / Math.max(1, implicitHeight)
                width: Math.min(image_pan.width, image_pan.height * ratio) * image_viewer.zoom
                height: width / Math.max(0.001, ratio)
                fillMode: Image.PreserveAspectFit; asynchronous: true; smooth: true; mipmap: true
            }
        }
    }

    NoteEditor {
        id: note_editor
        hostWindow: window; markerColors: s.marker_colors
        readerIdentity: (s.reader.link || "") + (s.reader.translated ? "|es" : "|original")
    }
    FileDialog { options: FileDialog.DontUseNativeDialog; id: category_icon_file; title: "Icono de la categoría"; nameFilters: ["Imágenes (*.png *.jpg *.jpeg *.webp *.svg *.ico)"]; onAccepted: category_dialog.icon_url = selectedFile.toString() }
    FileDialog { options: FileDialog.DontUseNativeDialog; id: icon_file; title: "Icono de la fuente"; nameFilters: ["Imágenes (*.png *.jpg *.jpeg *.webp)"]; onAccepted: source_dialog.icon_url=selectedFile.toString() }

    Dialog {
        id: quote_dialog; objectName: "quote_dialog"; anchors.centerIn: parent; modal: true; title: "Preparar imagen de la cita"; width: Math.min(820,window.width-30); height: Math.min(580,window.height-30)
        property int background_index: 0
        property var backgrounds: [{key: "", name: "Según el tema", start: "#171b20", end: "#171b20"}].concat(s.quote_backgrounds || [])
        property bool show_link: false; property bool show_source_icon: true
        property bool spanish: false; property bool title_spanish: false; property bool include_image: false; property int color_index: 0
        function regenerate() {quote_delay.restart();}
        onOpened: {background_index=Math.max(0,backgrounds.findIndex(b=>b.key==="choroy"));spanish=s.quote_is_translated;title_spanish=s.quote_title_has_translation && spanish;include_image=false;color_index=Math.max(0,s.themes.findIndex(t=>t.key===s.theme));regenerate();}
        background: Rectangle { color: p.panel; radius: 12; border.color: p.border }
        header: Label { textFormat: Text.PlainText; text: quote_dialog.title; padding: 18; color: p.text; font.bold: true; font.pixelSize: 17 }
        contentItem: RowLayout {
            spacing: 18
            ScrollView { id: quote_options; Layout.preferredWidth: 230; Layout.fillHeight: true; clip: true; contentWidth: availableWidth
            ColumnLayout { width: quote_options.availableWidth; spacing: 12
                Button { objectName: "quoteLanguageButton"; text: quote_dialog.spanish ? "Mostrar idioma original" : "Mostrar traducción"; onClicked: {
                    if (quote_dialog.spanish && !s.quote_has_original) quote_original_dialog.open();
                    else { quote_dialog.spanish = !quote_dialog.spanish; quote_dialog.regenerate(); }
                }
                    background: Rectangle { color: parent.hovered?p.hover:p.card; radius:6 } contentItem: Text { textFormat: Text.PlainText; text:parent.text;color:p.text;padding:10;wrapMode:Text.Wrap } Layout.fillWidth:true
                }
                CheckBox {
                    id: quote_title_language; text: "Título en español"
                    Layout.fillWidth: true; spacing: 8; enabled: s.quote_title_has_translation; checked: quote_dialog.title_spanish
                    onClicked: { quote_dialog.title_spanish=checked; quote_dialog.regenerate(); }
                    contentItem: Text { textFormat: Text.PlainText;
                        text: quote_title_language.text; color: quote_title_language.enabled ? p.text : p.muted
                        leftPadding: quote_title_language.indicator.width + quote_title_language.spacing
                        wrapMode: Text.Wrap; verticalAlignment: Text.AlignVCenter
                    }
                    indicator: Rectangle {
                        width: 20; height: 20; y: (quote_title_language.height-height)/2; radius: 4
                        color: quote_title_language.checked ? p.accent : p.card; border.color: p.muted
                        Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: quote_title_language.checked ? "✓" : ""; color: p.accent_text }
                    }
                }
                CheckBox {
                    id: quote_image_check; text: "Incluir imagen del artículo"
                    Layout.fillWidth: true; spacing: 8
                    enabled: s.quote_has_image; checked: quote_dialog.include_image
                    onClicked: {quote_dialog.include_image=checked;quote_dialog.regenerate();}
                    contentItem: Text { textFormat: Text.PlainText;
                        text: quote_image_check.text; color: quote_image_check.enabled ? p.text : p.muted
                        leftPadding: quote_image_check.indicator.width + quote_image_check.spacing
                        wrapMode: Text.Wrap; verticalAlignment: Text.AlignVCenter
                    }
                    indicator: Rectangle {
                        width: 20; height: 20; y: (quote_image_check.height-height)/2; radius: 4
                        color: quote_image_check.checked ? p.accent : p.card; border.color: p.muted
                        Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: quote_image_check.checked ? "✓" : ""; color: p.accent_text }
                    }
                }
                Check { objectName: "quoteShowLink"; text: "Mostrar enlace"; checked: quote_dialog.show_link; Layout.fillWidth: true; onClicked: { quote_dialog.show_link = checked; quote_dialog.regenerate(); } }
                Check { objectName: "quoteShowSourceIcon"; text: "Mostrar icono de la web"; checked: quote_dialog.show_source_icon; Layout.fillWidth: true; onClicked: { quote_dialog.show_source_icon = checked; quote_dialog.regenerate(); } }
                Label { textFormat: Text.PlainText; text: "Fondo de la cita"; color: p.text }
                ComboBox {
                    objectName: "quoteBackgroundSelector"
                    Layout.fillWidth: true; model: quote_dialog.backgrounds; textRole: "name"
                    currentIndex: quote_dialog.background_index
                    onActivated: { quote_dialog.background_index = currentIndex; quote_dialog.regenerate(); }
                }
                Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: 28; radius: 5
                    visible: quote_dialog.background_index > 0
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: quote_dialog.backgrounds[quote_dialog.background_index].start }
                        GradientStop { position: 1; color: quote_dialog.backgrounds[quote_dialog.background_index].end }
                    }
                }
                Button { visible: quote_dialog.background_index === 0; text:"Color " + s.themes[quote_dialog.color_index].name; Layout.fillWidth:true; onClicked:{quote_dialog.color_index=(quote_dialog.color_index+1)%s.themes.length;quote_dialog.regenerate();}
                    background:Rectangle { color:s.themes[quote_dialog.color_index].key==="periodico"?"#e6e6e6":"#232a34";radius:6 }
                    contentItem:Text { textFormat: Text.PlainText;text:parent.text;color:s.themes[quote_dialog.color_index].color;wrapMode:Text.Wrap;padding:10}
                }
                Label { textFormat: Text.PlainText; text:s.quote_busy?"Actualizando vista previa…":s.quote_is_translated && !s.quote_has_original?"Mostrar idioma original permite seleccionar las palabras exactas de la fuente.":"Vista previa · 2160 × 2160 · PNG o JPG"; color:p.muted; wrapMode:Text.Wrap; Layout.fillWidth:true }
            }
            }
            Image { source:s.quote_preview; Layout.fillWidth:true; Layout.fillHeight:true; fillMode:Image.PreserveAspectFit; smooth:true; mipmap:true; cache:false }
        }
        footer: RowLayout { Item {Layout.fillWidth:true} Button {text:"Cancelar";onClicked:quote_dialog.close()} Button {text:"Copiar enlace";onClicked:backend.copy_quote_link()} Button {text:"Guardar imagen…";enabled:s.quote_can_save;onClicked:quote_file.open()} Item {width:12} }
        Timer { id:quote_delay;interval:150;onTriggered:backend.update_quote(quote_dialog.spanish,quote_dialog.include_image,quote_dialog.title_spanish,s.themes[quote_dialog.color_index].key,quote_dialog.backgrounds[quote_dialog.background_index].key,quote_dialog.show_link,quote_dialog.show_source_icon) }
    }
    FileDialog { options: FileDialog.DontUseNativeDialog; id: opml_import_file; title: "Importar fuentes y categorías"; nameFilters: ["Fuentes OPML (*.opml *.xml)"]; onAccepted: backend.portability_action("import_opml", selectedFile.toString()) }
    FileDialog { options: FileDialog.DontUseNativeDialog; id: opml_export_file; title: "Exportar fuentes y categorías"; fileMode: FileDialog.SaveFile; defaultSuffix: "opml"; nameFilters: ["Fuentes OPML (*.opml)"]; onAccepted: backend.portability_action("export_opml", selectedFile.toString()) }
    FileDialog { options: FileDialog.DontUseNativeDialog; id: backup_export_file; title: "Crear copia de seguridad local"; fileMode: FileDialog.SaveFile; defaultSuffix: "zip"; nameFilters: ["Copia de Choroy Reader (*.zip)"]; onAccepted: backend.portability_action("backup", selectedFile.toString()) }
    FileDialog { options: FileDialog.DontUseNativeDialog; id: backup_import_file; title: "Restaurar copia de seguridad"; nameFilters: ["Copia de Choroy Reader (*.zip)"]; onAccepted: { restore_confirmation.backup_url = selectedFile.toString(); restore_confirmation.open(); } }
    Dialog {
        id: restore_confirmation; anchors.centerIn: parent; modal: true; width: Math.min(480, window.width - 40)
        property string backup_url: ""
        title: "Restaurar datos locales"
        background: Rectangle { color: p.panel; radius: 10; border.color: p.border }
        header: Label { textFormat: Text.PlainText; text: restore_confirmation.title; color: p.text; font.bold: true; padding: 16 }
        contentItem: ColumnLayout {
            Label { textFormat: Text.PlainText; text: "Se reemplazarán las fuentes, preferencias, estados y colecciones actuales por los de la copia. Antes se guardará una copia automática del estado actual en la carpeta backups. El archivo se validará antes de modificar tus datos."; color: p.text; wrapMode: Text.Wrap; Layout.fillWidth: true }
            RowLayout {
                Action { text: "Cancelar"; onClicked: restore_confirmation.close() }
                Action { text: "Restaurar"; enabled: s.portability_ready; active: true; onClicked: { restore_confirmation.close(); backend.portability_action("restore", restore_confirmation.backup_url); } }
            }
        }
    }
    Popup {
        anchors.centerIn: parent; modal: true; visible: s.portability_busy; closePolicy: Popup.NoAutoClose
        background: Rectangle { color: p.panel; radius: 10; border.color: p.border }
        contentItem: Label { textFormat: Text.PlainText; text: "Procesando archivo local…"; color: p.text; padding: 20 }
    }
    Dialog {
        id: quote_original_dialog; objectName: "quoteOriginalDialog"; anchors.centerIn: parent
        modal: true; title: "Seleccionar fragmento original"
        width: Math.min(720, window.width - 40); height: Math.min(560, window.height - 40)
        onOpened: original_quote_text.deselect()
        contentItem: ColumnLayout {
            Label { textFormat: Text.PlainText; text: "Selecciona el pasaje original correspondiente a tu cita (hasta 500 caracteres)."; wrapMode: Text.Wrap; Layout.fillWidth: true; color: p.text }
            ScrollView {
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                TextArea { id: original_quote_text; objectName: "quoteOriginalText"; text: s.quote_original_body || ""; readOnly: true; selectByMouse: true; persistentSelection: true; wrapMode: TextEdit.Wrap; textFormat: TextEdit.PlainText; color: p.text; selectionColor: p.accent }
            }
            Label { textFormat: Text.PlainText; text: original_quote_text.selectedText.length + " / 500 caracteres"; color: p.muted }
        }
        footer: RowLayout {
            Item { Layout.fillWidth: true }
            Button { text: "Cancelar"; onClicked: quote_original_dialog.close() }
            Button { objectName: "useOriginalQuote"; text: "Usar selección"; enabled: original_quote_text.selectedText.trim().length > 0 && original_quote_text.selectedText.trim().length <= 500
                onClicked: { if (backend.set_quote_original(original_quote_text.selectedText)) { quote_original_dialog.close(); quote_dialog.spanish = false; quote_dialog.regenerate(); } }
            }
        }
    }
    FileDialog { options: FileDialog.DontUseNativeDialog; id:quote_file;title:"Guardar cita";fileMode:FileDialog.SaveFile;currentFolder:s.downloads_folder;nameFilters:["Imagen PNG (*.png)","Imagen JPG (*.jpg *.jpeg)"];defaultSuffix:selectedNameFilter.index===1?"jpg":"png";onAccepted:backend.export_quote(selectedFile.toString()) }
    Dialog { id:error_dialog;anchors.centerIn:parent;modal:true;title:"Choroy Reader";standardButtons:Dialog.Ok;width:Math.min(480,window.width-40)
        property string message:""
        Label { textFormat: Text.PlainText;text:error_dialog.message;wrapMode:Text.Wrap;width:parent.width;color:p.text}
        background:Rectangle {color:p.panel;radius:8;border.color:p.border}
    }
    Connections {target:backend;function onError(message){error_dialog.message=message;error_dialog.open();}}
}
