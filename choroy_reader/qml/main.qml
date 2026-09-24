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
    title: "Choroy Reader"
    property var s: backend.state
    property var p: s.palette
    property real feed_scroll: 0
    property bool sidebar_visible: true
    property var expanded_categories: ({})
    color: p.bg
    font.family: "Sans Serif"
    font.pixelSize: 13

    component Action: Button {
        id: control
        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
        property bool active: false
        property bool compact: false
        property string symbol: ""
        property bool warning: false
        property string favicon: ""
        leftPadding: 12; rightPadding: 12; topPadding: compact ? 5 : 9; bottomPadding: compact ? 5 : 9
        implicitHeight: Math.max(32, contentItem.implicitHeight + topPadding + bottomPadding)
        background: Rectangle { radius: 6; color: control.warning ? (p.light ? "#f0dcdc" : "#39272a") : control.down ? Qt.lighter(p.hover, 1.35) : control.hovered ? Qt.lighter(p.hover, 1.2) : control.active ? p.hover : "transparent"; border.color: control.visualFocus ? p.accent : "transparent" }
        contentItem: RowLayout { spacing: 10
            Image { visible: control.favicon.length > 0; source: control.favicon; Layout.preferredWidth: 18; Layout.preferredHeight: 18; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true }
            Glyph { visible: control.symbol.length > 0; kind: control.symbol; ink: p.accent; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
            Text { Layout.fillWidth: true; text: control.text; color: !control.enabled ? p.muted : control.active ? p.accent : p.text; font: control.font; wrapMode: Text.Wrap; verticalAlignment: Text.AlignVCenter }
        }
    }
    component Search: TextField {
        id: field
        implicitHeight: 38
        leftPadding: 14; rightPadding: 14
        color: p.text; placeholderTextColor: p.muted; selectionColor: p.accent; selectedTextColor: p.accent_text
        background: Rectangle { color: p.hover; radius: 18; border.width: 1; border.color: field.activeFocus ? p.accent : p.border }
    }
    component SettingsChoice: ComboBox {
        id: choice
        implicitHeight: 38
        background: Rectangle { radius: 8; color: p.hover; border.color: choice.activeFocus ? p.accent : p.border }
        contentItem: Text { text: choice.displayText; color: p.text; leftPadding: 12; rightPadding: 30; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
        indicator: Text { text: "⌄"; color: p.accent; x: parent.width - width - 12; y: (parent.height - height)/2 }
        delegate: ItemDelegate {
            required property int index
            required property var modelData
            width: choice.width
            contentItem: Text { text: modelData; color: choice.currentIndex === index ? p.accent : p.text; elide: Text.ElideRight }
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
        contentItem: Text { text: check.text; color: p.text; leftPadding: check.indicator.width + check.spacing; verticalAlignment: Text.AlignVCenter; wrapMode: Text.Wrap }
        indicator: Rectangle { x: 0; y: (check.height-height)/2; width: 20; height: 20; radius: 5; color: check.checked ? p.accent : p.hover; border.color: p.border
            Text { anchors.centerIn: parent; text: check.checked ? "✓" : ""; color: p.accent_text }
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
        background: Rectangle { anchors.centerIn: parent; width: 34; height: 34; radius: 6; color: icon_control.stateActive ? "#62834b" : icon_control.hovered ? p.hover : p.card; border.width: icon_control.stateActive ? 2 : 1; border.color: icon_control.stateActive ? "#9cbd78" : icon_control.visualFocus ? p.accent : p.border }
        contentItem: Item {
            Glyph { anchors.centerIn: parent; width: 20; height: 20; kind: icon_control.kind; ink: icon_control.stateActive ? "#ffffff" : icon_control.kind === "delete" ? (p.light ? "#b3261e" : "#ff8a80") : p.accent; filled: icon_control.filled; opacity: icon_control.enabled ? 1 : 0.4 }
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
        Label {
            id: radar_badge_text
            anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            anchors.margins: 8
            text: !radar_badge.article.radar ? "◎ Radar · Sin coincidencias" : radar_hover.hovered ? "◎ Radar · " + (radar_badge.article.radar_detected || []).join(", ") : "◎ Radar detectado · " + radar_badge.article.interests + (radar_badge.article.interests === 1 ? " interés" : " intereses") + " · " + radar_badge.article.mentions + (radar_badge.article.mentions === 1 ? " mención" : " menciones")
            color: radar_badge.radar_color; font.bold: true; font.pixelSize: 11; elide: Text.ElideRight
        }
    }

    component SectionTitle: Label { color: p.text; font.pixelSize: 17; font.bold: true; wrapMode: Text.Wrap }

    ColumnLayout {
        anchors.fill: parent; spacing: 0
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 84; color: p.bg
            Action {
                objectName: "sidebarToggle"
                anchors.left: parent.left; anchors.leftMargin: 14; anchors.verticalCenter: parent.verticalCenter
                text: "☰"; onClicked: window.sidebar_visible = !window.sidebar_visible
                Accessible.name: window.sidebar_visible ? "Ocultar menú lateral" : "Mostrar menú lateral"
                ToolTip.visible: hovered; ToolTip.text: Accessible.name
            }
            RowLayout {
                anchors.centerIn: parent; spacing: 14
                Image { objectName: "appLogo"; source: s.logo; Layout.preferredWidth: 64; Layout.preferredHeight: 64; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true }
                ColumnLayout {
                    Label { text: "Tus fuentes. Tu feed. Sin distracciones."; color: p.accent; font.bold: true; font.pixelSize: 15; Layout.alignment: Qt.AlignHCenter; wrapMode: Text.Wrap; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
                    Rectangle { Layout.preferredWidth: 100; Layout.preferredHeight: 2; color: p.accent; Layout.alignment: Qt.AlignHCenter }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
            Rectangle {
                objectName: "sidebarPanel"; visible: window.sidebar_visible
                Layout.preferredWidth: 280; Layout.fillHeight: true; color: p.panel
                ColumnLayout {
                    anchors.fill: parent; spacing: 2
                    ScrollView {
                        id: side_scroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                        contentWidth: availableWidth
                        ColumnLayout {
                            width: side_scroll.availableWidth; spacing: 4
                            Action { objectName: "articlesNavigation"; Layout.preferredHeight: 38; symbol: "articles"; text: "Todos los artículos"; active: s.page === "feed" && s.category === ""; Layout.fillWidth: true; Layout.margins: 14; onClicked: backend.navigate("feed", "", "") }
                            Action { symbol: "save"; text: "Guardados"; active: s.page === "guardados"; Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; onClicked: backend.navigate("guardados", "", "") }
                            Action { symbol: "articles"; text: "Historial"; active: s.page === "historial"; Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; onClicked: backend.navigate("historial", "", "") }
                            Action { symbol: "archive"; text: "Archivados"; active: s.page === "archivados"; Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; onClicked: backend.navigate("archivados", "", "") }
                            Action { symbol: "download"; text: "Descargas"; active: s.page === "descargas"; Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; onClicked: backend.navigate("descargas", "", "") }
                            RowLayout {
                                Layout.fillWidth: true; Layout.margins: 18
                                Label { text: "Radar de intereses"; color: p.text; Layout.fillWidth: true }
                                Switch {
                                    id: radar_switch; objectName: "radar_switch"; checked: s.radar; onClicked: backend.toggle_radar(); padding: 0
                                    indicator: Rectangle { width: 42; height: 24; radius: 12; color: radar_switch.checked ? ((s.theme === "gris" || s.theme === "periodico") ? "#62834b" : p.accent) : "#777b82"
                                        Rectangle { x: radar_switch.checked ? 21 : 3; y: 3; width: 18; height: 18; radius: 9; color: "#f0f0f0"; Behavior on x { NumberAnimation { duration: 110 } } }
                                    }
                                }
                            }
                            Label { text: "TUS CATEGORÍAS"; color: p.muted; font.pixelSize: 10; font.bold: true; Layout.leftMargin: 22; Layout.bottomMargin: 5 }
                            Repeater {
                                model: s.categories
                                delegate: ColumnLayout {
                                    id: category_delegate; required property var modelData
                                    property bool expanded: !!window.expanded_categories[modelData.name]
                                    Layout.fillWidth: true; spacing: 2
                                    Action { text: (category_delegate.expanded ? "⌄  " : "›  ") + category_delegate.modelData.name + "  ·  " + category_delegate.modelData.sources.length; active: s.category === category_delegate.modelData.name; Layout.fillWidth: true; Layout.leftMargin: 12; Layout.rightMargin: 12; onClicked: {const next=Object.assign({},window.expanded_categories);next[category_delegate.modelData.name]=!category_delegate.expanded;window.expanded_categories=next;} }
                                    ColumnLayout {
                                        visible: category_delegate.expanded; Layout.fillWidth: true; Layout.leftMargin: 28; Layout.rightMargin: 12; spacing: 1
                                        Action { text: "Todas las fuentes"; compact: true; Layout.fillWidth: true; onClicked: backend.navigate("feed",category_delegate.modelData.name,"") }
                                        Repeater { model: category_delegate.modelData.sources
                                            delegate: Action {
                                                id: source_button
                                                required property var modelData
                                                text: modelData.name + (modelData.shortcut ? " ↗" : modelData.no_feed ? " · Sin feed" : "")
                                                favicon: modelData.icon; warning: modelData.no_feed; compact: true
                                                active: s.source === modelData.url; Layout.fillWidth: true
                                                onClicked: modelData.shortcut ? backend.open_url(modelData.url) : backend.navigate("feed",category_delegate.modelData.name,modelData.url)
                                                TapHandler { acceptedButtons: Qt.RightButton; onTapped: source_menu.popup() }
                                                Menu {
                                                    id: source_menu
                                                    MenuItem { text: "Abrir sitio web ↗"; onTriggered: backend.open_url(source_button.modelData.url) }
                                                    MenuItem { text: "Editar fuente…"; onTriggered: source_dialog.edit(category_delegate.modelData.index, source_button.modelData) }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            Item { height: 12; Layout.fillWidth: true }
                        }
                    }
                    Rectangle { Layout.fillWidth: true; Layout.margins: 18; height: 1; color: p.border }
                    ColumnLayout {
                        Layout.fillWidth: true; Layout.margins: 14; Layout.alignment: Qt.AlignTop; spacing: 1
                        Label {
                            text: "CONFIGURACIÓN"; color: p.muted; font.pixelSize: 10; font.bold: true
                            Layout.leftMargin: 12; Layout.bottomMargin: 5
                        }
                        Action { objectName: "designNavigation"; Layout.preferredHeight: 38; text: "Diseño"; active: s.page === "design"; Layout.fillWidth: true; onClicked: backend.navigate("design", "", "") }
                        Action { text: "Gestionar fuentes y categorías"; active: s.page === "sources"; Layout.fillWidth: true; onClicked: backend.navigate("sources", "", "") }
                        Action { text: "Configurar radar"; active: s.page === "radar"; Layout.fillWidth: true; onClicked: backend.navigate("radar", "", "") }
                    }
                    Rectangle { Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22; height: 1; color: p.border }
                    RowLayout {
                        Layout.leftMargin: 18; Layout.rightMargin: 18; spacing: 8
                        Repeater { model: ["GitHub", "Instagram", "X", "Mastodon"]
                            delegate: Button {
                                id: social_button
                                required property string modelData
                                implicitWidth: 34; implicitHeight: 34; padding: 0
                                Layout.minimumWidth: 34; Layout.maximumWidth: 34
                                Layout.minimumHeight: 34; Layout.maximumHeight: 34
                                topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
                                Accessible.name: modelData + " del autor (próximamente)"
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
                                        else if(social_button.modelData==="X") {c.beginPath();c.moveTo(4,3);c.lineTo(18,21);c.lineTo(21,21);c.lineTo(7,3);c.closePath();c.moveTo(20,3);c.lineTo(4,21);c.stroke();}
                                        else if(social_button.modelData==="GitHub") {c.beginPath();c.moveTo(5,8);c.lineTo(5,3);c.lineTo(10,6);c.lineTo(14,6);c.lineTo(19,3);c.lineTo(19,8);c.bezierCurveTo(24,17,17,20,12,20);c.bezierCurveTo(7,20,0,17,5,8);c.stroke();c.moveTo(10,20);c.lineTo(10,24);c.moveTo(14,20);c.lineTo(14,24);c.stroke();}
                                        else {c.strokeRect(2,3,20,16);c.beginPath();c.moveTo(3,19);c.lineTo(6,23);c.lineTo(16,23);c.moveTo(6,15);c.lineTo(6,8);c.lineTo(9,7);c.lineTo(12,10);c.lineTo(15,7);c.lineTo(18,8);c.lineTo(18,15);c.moveTo(12,10);c.lineTo(12,15);c.stroke();}
                                    }
                                  }
                                }
                            }
                        }
                    }
                    Label { text: s.radar_busy ? "Radar: analizando contenido…" : s.status; color: p.muted; wrapMode: Text.Wrap; font.pixelSize: 10; Layout.fillWidth: true; Layout.margins: 18 }
                }
            }
            Loader {
                id: main_loader; Layout.fillWidth: true; Layout.fillHeight: true
                sourceComponent: s.reader.link ? reader_page : s.page === "design" ? design_page : s.page === "radar" ? radar_page : s.page === "sources" ? sources_page : feed_page
            }
        }
    }

    Component {
        id: feed_page
        ColumnLayout {
            spacing: 8
            RowLayout {
                Layout.fillWidth: true; Layout.margins: 14; spacing: 10
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
                        Text {
                            text: "↻"; color: "#ffffff"; font.pixelSize: 22
                            visible: s.busy
                            RotationAnimator on rotation { from: 0; to: 360; duration: 1100; loops: Animation.Infinite; running: s.busy && !s.refresh_cancelling }
                        }
                        Text {
                            text: refresh_button.text; font.bold: true; color: "#ffffff"
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
                Button {
                    id: mark_all_button; objectName: "markAllReadButton"
                    Layout.preferredHeight: 38; leftPadding: 12; rightPadding: 12
                    text: "Leídos ▾"
                    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
                    Accessible.name: "Marcar todos como leídos"
                    ToolTip.visible: hovered; ToolTip.text: Accessible.name
                    background: Rectangle {
                        radius: 10; color: mark_all_button.hovered ? "#343a40" : "#24282d"
                        border.color: mark_all_button.visualFocus ? p.accent : "#50565e"
                    }
                    contentItem: Text {
                        text: mark_all_button.text; color: "#ffffff"; font.bold: true
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: read_scope_menu.popup()
                    Menu {
                        id: read_scope_menu
                        MenuItem { text: "Marcar todos como leídos"; enabled: false }
                        MenuSeparator {}
                        MenuItem {
                            visible: !!s.read_undo.count; height: visible ? implicitHeight : 0
                            text: "Deshacer · " + (s.read_undo.scope || "")
                            onTriggered: backend.undo_mark_all_read()
                        }
                        MenuItem { text: "Esta fuente…"; visible: s.source.length > 0; height: visible ? implicitHeight : 0; onTriggered: { backend.prepare_mark_all_read("source"); bulk_read_dialog.open(); } }
                        MenuItem { text: "Esta categoría…"; visible: s.category.length > 0; height: visible ? implicitHeight : 0; onTriggered: { backend.prepare_mark_all_read("category"); bulk_read_dialog.open(); } }
                        MenuItem { text: "Biblioteca completa…"; onTriggered: { backend.prepare_mark_all_read("library"); bulk_read_dialog.open(); } }
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
                        Text {
                            text: offline_button.text; font.bold: true
                            color: offline_button.enabled ? "#ffffff" : "#a0a5ac"
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        }
                    }
                    ToolTip.visible: hovered
                    ToolTip.text: s.bulk_busy ? "Cancelar y eliminar las descargas nuevas de esta operación. Se conservan las anteriores." : "Descarga todos los artículos cargados para leerlos sin conexión."
                }
                Search { objectName: "titleSearch"; Layout.fillWidth: true; Layout.minimumWidth: 60; placeholderText: "Buscar en títulos"; text: s.query; onTextEdited: title_search_delay.restart()
                    Timer { id: title_search_delay; interval: 180; onTriggered: backend.search_titles(parent.text) }
                }
            }
            RowLayout {
                id: interest_strip
                visible: s.page === "feed" && s.link_sources.length > 0
                Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; spacing: 6
                property bool overflowing: interest_row.implicitWidth > width
                Action {
                    text: "‹"; compact: true; visible: interest_strip.overflowing
                    enabled: interest_links.contentX > 0
                    Accessible.name: "Fuentes anteriores"
                    onClicked: interest_links.contentX = Math.max(0, interest_links.contentX-interest_links.width*0.8)
                }
                Flickable {
                    id: interest_links; Layout.fillWidth: true; Layout.preferredHeight: 34
                    clip: true; contentWidth: interest_row.implicitWidth; contentHeight: height
                    flickableDirection: Flickable.HorizontalFlick; boundsBehavior: Flickable.StopAtBounds
                    onContentWidthChanged: contentX = Math.max(0, Math.min(contentX, contentWidth-width))
                    onWidthChanged: contentX = Math.max(0, Math.min(contentX, contentWidth-width))
                    Row {
                        id: interest_row; spacing: 6
                        Repeater { model: s.link_sources
                            delegate: Action {
                                required property var modelData
                                text: modelData.name + " ↗"; favicon: modelData.icon; warning: modelData.no_feed; compact: true
                                onClicked: backend.open_url(modelData.url)
                                ToolTip.visible: hovered
                                ToolTip.text: modelData.no_feed ? "Sin feed detectado · Abrir sitio web" : "Atajo web · Abrir sitio"
                                ToolTip.delay: 500
                            }
                        }
                    }
                }
                Action {
                    text: "›"; compact: true; visible: interest_strip.overflowing
                    enabled: interest_links.contentX < interest_links.contentWidth-interest_links.width-1
                    Accessible.name: "Fuentes siguientes"
                    onClicked: interest_links.contentX = Math.max(0, Math.min(interest_links.contentWidth-interest_links.width, interest_links.contentX+interest_links.width*0.8))
                }
            }
            Label { text: s.page === "descargas" ? "Descargas · Sin conexión" : s.page === "guardados" ? "Guardados" : s.page === "archivados" ? "Archivados" : s.page === "historial" ? "Historial" : s.page === "retirados" ? "Historial retirado · Recuperable durante 30 días" : s.category; visible: text.length > 0; color: p.accent; font.bold: true; Layout.leftMargin: 18 }
            Action {text: "Abrir sitio de la fuente ↗"; visible:s.source.length>0; Layout.leftMargin:18; compact:true; onClicked:backend.open_url(s.source)}
            Label {
                visible: s.page === "historial"
                text: "Artículos recibidos, aunque ya no aparezcan en el RSS. Se conservan sus estados; para garantizar la lectura sin conexión, descárgalos."
                color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
            }
            ScrollView {
                id: feed_scroll_view; Component.onCompleted: Qt.callLater(function(){feed_scroll_view.contentItem.contentY=window.feed_scroll;}); Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth
                ColumnLayout {
                    width: feed_scroll_view.availableWidth; spacing: 10
                    Label { text: s.busy ? "Cargando artículos e imágenes…" : s.query ? "No hay títulos que coincidan." : "No hay artículos en esta sección."; visible: s.articles.length === 0; color: p.muted; Layout.fillWidth: true; Layout.margins: 20; wrapMode: Text.Wrap }
                    GridLayout {
                        id: cards_grid;
                        property real card_height: children.reduce(function(height, child) { return Math.max(height, child.implicitHeight || 0); }, 0)
                         Layout.fillWidth: true; Layout.margins: 12; columns: Math.max(1,Math.min(s.columns,Math.floor((feed_scroll_view.availableWidth-24)/240))); columnSpacing: 8; rowSpacing: 8
                        Repeater {
                            model: s.articles
                            delegate: Rectangle {
                                id: card; required property var modelData
                                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 1; Layout.preferredHeight: cards_grid.card_height
                                implicitHeight: card_body.implicitHeight + 2; color: p.card; radius: 2
                                border.color: card_hover.hovered ? p.accent : p.border; border.width: 1
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
                                            IconAction { kind: "archive"; stateActive: card.modelData.archived; hint: card.modelData.archived ? "Restaurar al feed" : "Archivar artículo"; onClicked: backend.toggle_archived(card.modelData.link) }
                                            IconAction { kind: "save"; filled: card.modelData.saved; hint: filled ? "Quitar guardado" : "Guardar artículo"; onClicked: backend.toggle_saved(card.modelData.link) }
                                            IconAction { kind: card.modelData.downloaded ? "delete" : "download"; filled: card.modelData.downloaded; enabled: !card.modelData.downloading; hint: filled ? "Eliminar descarga" : "Descargar para leer sin conexión"; onClicked: backend.toggle_download(card.modelData.link) }
                                        }
                                HoverHandler { id: card_hover }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: {window.feed_scroll=feed_scroll_view.contentItem.contentY;backend.open_article(card.modelData.link);} }
                                ColumnLayout {
                                    id: card_body; anchors.fill: parent; anchors.margins: 1; spacing: 0
                                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: cards_grid.columns === 1 ? 200 : 150; color: p.hover; clip: true
                                        Image { anchors.fill: parent; source: card.modelData.image; fillMode: Image.PreserveAspectCrop; asynchronous: true; smooth: true; mipmap: true }
                                        Label { anchors.centerIn: parent; visible: card.modelData.image === ""; text: "Imagen no disponible"; color: p.muted; font.pixelSize: 11 }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true; Layout.fillHeight: true; Layout.margins: 12; spacing: 8
                                        RadarBadge { article: card.modelData }
                                        RowLayout { Layout.fillWidth: true
                                            Label { text: card.modelData.source; color: p.accent; font.bold: true; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                                            Label { text: card.modelData.date; color: p.muted; font.pixelSize: 10 }
                                        }
                                        Text { text: card.modelData.title_html; textFormat: Text.RichText; color: card.modelData.seen || card.modelData.dismissed ? p.muted : p.text; font.pixelSize: cards_grid.columns === 1 ? 15 : 13; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                        RowLayout { visible: card.modelData.show_translation && card.modelData.translation.length > 0; Layout.fillWidth: true; spacing: 6
                                            Rectangle { width: 16; height: 16; radius: 8; color: "#c9293b"; Layout.alignment: Qt.AlignTop
                                                Rectangle { anchors.centerIn: parent; width: 15; height: 7; radius: 1; color: "#f6c645" }
                                            }
                                            Text { text: card.modelData.translation_html; textFormat: Text.RichText; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 13 }
                                        }
                                        Action { visible: s.page === "retirados"; text: "Recuperar historial"; active: true; Layout.fillWidth: true; onClicked: backend.restore_history(card.modelData.link) }
                                        Label {
                                            visible: card.modelData.reading_progress.position !== undefined
                                            text: "Continuar lectura · " + (card.modelData.reading_progress.percent || 0) + "%"
                                            color: p.muted; font.pixelSize: 11; Layout.fillWidth: true
                                        }
                                        Label { visible: card.modelData.dismissed; text: "Descartado · No me interesa"; color: p.muted; font.bold: true; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                        Item { Layout.fillHeight: true; Layout.minimumHeight: 0 }
                                        Item { Layout.fillWidth: true; Layout.preferredHeight: 34 }
                                    }
                                }
                            }
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
            property string marker_color: p.light ? "#ffe88f" : p.accent
            property int mark_anchor: 0
            property int menu_position: 0
            property string selected_quote: ""
            ColumnLayout {
                id: reader_content
                width: reader_scroll.availableWidth; spacing: 12
                Action { text: "← Volver al feed"; Layout.leftMargin: 16; Layout.topMargin: 12; onClicked: backend.close_article() }
                RowLayout { Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                    Search { id: body_search; objectName: "body_search"; placeholderText: "Buscar en artículo"; Layout.fillWidth: true; Layout.minimumWidth: 80; onTextEdited: backend.search_document(text); onAccepted: backend.next_match() }
                    Action { text: s.reader.translating ? "Traduciendo…" : s.reader.translated ? "Ver original" : "Leer en español"; active: true; enabled: s.reader.ready && !s.reader.translating; onClicked: backend.translate_article() }
                    Action { text: "Abrir original ↗"; onClicked: backend.open_url(s.reader.link) }
                }
                Image { source: s.reader.image || ""; visible: s.reader.show_image && source.toString().length > 0; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; Layout.preferredHeight: visible ? Math.min(280,width*9/16) : 0; fillMode: Image.PreserveAspectCrop; clip: true; smooth: true; mipmap: true }
                RowLayout { Layout.leftMargin: 18; Layout.rightMargin: 18; Layout.fillWidth: true
                    IconAction { kind: "dismiss"; stateActive: !!s.reader.dismissed; hint: s.reader.dismissed ? "Deshacer descarte" : "No me interesa · Volver al feed"; onClicked: backend.toggle_dismissed(s.reader.link) }
                    IconAction { kind: "archive"; stateActive: !!s.reader.archived; hint: s.reader.archived ? "Restaurar al feed" : "Archivar artículo"; onClicked: backend.toggle_archived(s.reader.link) }
                    IconAction { kind: "save"; filled: !!s.reader.saved; hint: filled ? "Quitar guardado" : "Guardar"; onClicked: backend.toggle_saved(s.reader.link) }
                    IconAction { kind: s.reader.downloaded ? "delete" : "download"; filled: !!s.reader.downloaded; enabled: !s.reader.downloading; hint: filled ? "Eliminar descarga" : "Descargar"; onClicked: backend.toggle_download(s.reader.link) }
                    RadarBadge { objectName: "readerRadarBadge"; article: s.reader; visible: s.radar; Layout.minimumWidth: 100 }
                }
                RowLayout {
                    visible: s.reader.reading_progress && s.reader.reading_progress.position !== undefined
                    Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22
                    Label { text: "Punto de lectura guardado · " + (s.reader.reading_progress ? s.reader.reading_progress.percent || 0 : 0) + "%"; color: p.accent; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    Action { objectName: "resumeReadingButton"; text: "Continuar desde aquí"; active: true; enabled: s.reader.ready; onClicked: backend.resume_reading() }
                }
                SectionTitle { text: s.reader.title || ""; font.pixelSize: 23; Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22 }
                Label { text: (reader_scroll.marking ? "Destacador activo · Arrastra para marcar. " : "") + (s.reader.status || ""); color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22 }
                TextEdit {
                    id: article_text; objectName: "article_text"; Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22; Layout.bottomMargin: 28
                    text: s.reader.body || ""; textFormat: TextEdit.PlainText; readOnly: true; selectByMouse: !reader_scroll.marking; persistentSelection: true
                    wrapMode: TextEdit.Wrap; color: p.text; font.pixelSize: 16; selectionColor: p.accent; selectedTextColor: p.accent_text
                    property string attached_text: ""
                    property string document_identity: (s.reader.link || "") + (s.reader.translated ? "|es" : "|original")
                    onDocument_identityChanged: Qt.callLater(function(){backend.attach_document(article_text.textDocument);})
                    onTextChanged: {
                        if (text !== attached_text) {
                            attached_text = text;
                            Qt.callLater(function(){backend.attach_document(article_text.textDocument); body_search.text="";});
                        }
                    }
                    Component.onCompleted: backend.attach_document(textDocument)
                    MouseArea {
                        anchors.fill: parent; enabled: reader_scroll.marking; acceptedButtons: Qt.LeftButton; cursorShape: Qt.PointingHandCursor
                        preventStealing: true
                        function preview(x, y) {
                            const end = article_text.positionAt(x, y);
                            article_text.select(Math.min(reader_scroll.mark_anchor, end), Math.max(reader_scroll.mark_anchor, end));
                        }
                        onPressed: function(mouse){ reader_scroll.mark_anchor = article_text.positionAt(mouse.x,mouse.y); article_text.deselect(); }
                        onPositionChanged: function(mouse){ if(pressed) preview(mouse.x, mouse.y); }
                        onReleased: function(mouse){
                            const end = article_text.positionAt(mouse.x,mouse.y);
                            article_text.deselect();
                            backend.mark(reader_scroll.mark_anchor,end,reader_scroll.marker_color);
                        }
                        onCanceled: article_text.deselect()
                    }
                    MouseArea {
                        anchors.fill: parent; acceptedButtons: Qt.RightButton
                        onClicked: function(mouse){reader_scroll.menu_position=article_text.positionAt(mouse.x,mouse.y);reader_scroll.selected_quote=article_text.selectedText;article_menu.popup();}
                    }
                    Menu {
                        id: article_menu
                        MenuItem { text: "Guardar punto de lectura aquí"; onTriggered: backend.save_reading_position(reader_scroll.menu_position) }
                        MenuSeparator {}
                        MenuItem { text: "Crear imagen de la cita…"; enabled: reader_scroll.selected_quote.length > 0; onTriggered: {backend.prepare_quote(reader_scroll.selected_quote);if(reader_scroll.selected_quote.length<=500)quote_dialog.open();} }
                        Menu {
                            title: "Destacador"
                            Repeater { model: s.themes
                                delegate: MenuItem { required property var modelData; visible: modelData.key !== "periodico"; text: "●  " + modelData.name
                                    contentItem: Text { text: parent.text; color: modelData.color; font.pixelSize: 13; padding: 5 }
                                    onTriggered: {reader_scroll.marker_color=modelData.color;reader_scroll.marking=true;article_text.deselect();}
                                }
                            }
                            MenuItem { text: "Destacar selección"; enabled: article_text.selectionEnd > article_text.selectionStart; onTriggered: backend.mark(article_text.selectionStart,article_text.selectionEnd,reader_scroll.marker_color) }
                            MenuSeparator {}
                            MenuItem { text: "Desactivar destacador"; onTriggered: reader_scroll.marking=false }
                        }
                        MenuItem { text: "Quitar destacado"; onTriggered: {if(article_text.selectionEnd>article_text.selectionStart)backend.mark(article_text.selectionStart,article_text.selectionEnd,"");else backend.remove_mark_at(reader_scroll.menu_position);} }
                    }
                }
                Action {
                    objectName: "readerReadAction"
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
            Label { id: search_count; color: p.muted; font.pixelSize: 10; anchors.right: parent.right; anchors.top: parent.top }
        }
    }

    Component {
        id: design_page
        ScrollView { id: design_scroll; clip: true; contentWidth: availableWidth
            ColumnLayout { width: design_scroll.availableWidth; spacing: 16
                SectionTitle { text: "Diseño"; Layout.margins: 18 }
                Check { text: "Mostrar imágenes dentro de los artículos"; checked: s.show_images; Layout.leftMargin: 18; onClicked: backend.set_design(s.columns,checked,s.translate_titles) }
                Check { text: "Mostrar traducción de los títulos"; checked: s.translate_titles; Layout.leftMargin: 18; onClicked: backend.set_design(s.columns,s.show_images,checked) }
                RowLayout { Layout.leftMargin: 18
                    Label { text: "Artículos por fila (máximo)"; color: p.text }
                    SpinBox { from: 1; to: 5; value: s.columns; onValueModified: backend.set_design(value,s.show_images,s.translate_titles) }
                }
                SectionTitle { text: "Tema"; Layout.leftMargin: 18 }
                Flow { Layout.fillWidth: true; Layout.margins: 18; spacing: 8
                    Repeater { model: s.themes
                        delegate: Button { required property var modelData; text: modelData.name; onClicked: backend.set_theme(modelData.key); padding: 12
                            background: Rectangle { radius: 6; color: modelData.key === "periodico" ? "#e6e6e6" : "#232323"; border.width: s.theme === modelData.key ? 2 : 1; border.color: modelData.color }
                            contentItem: Text { text: parent.text; color: modelData.color }
                        }
                    }
                }
                Label { text: "Las fuentes se actualizan al iniciar y al pulsar Actualizar feed."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.margins: 18 }
            }
        }
    }
    Component {
        id: radar_page
        ScrollView { id: radar_scroll; clip: true; contentWidth: availableWidth
            ColumnLayout { width: radar_scroll.availableWidth; spacing: 14
                SectionTitle { text: "Radar de intereses"; Layout.margins: 18 }
                Label { text: "El radar busca tus intereses en los títulos y el contenido, y coloca primero los artículos más relevantes. Actívalo desde la barra lateral.\n\n◎ Un interés · ◎◎ Dos · ◎◎◎ Tres o más"; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18 }
                Check {
                    objectName: "radarBilingualToggle"
                    text: "Buscar también en inglés y español"; checked: s.radar_bilingual
                    Layout.leftMargin: 18; Layout.rightMargin: 18; Layout.alignment: Qt.AlignLeft
                    Layout.maximumWidth: radar_scroll.availableWidth - 36
                    onClicked: backend.set_radar_bilingual(checked)
                }
                Label {
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
                                    contentItem: Text { text: parent.text; color: p.text; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
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
                Label { visible: s.radar_words.length === 0; text: "Agrega tu primer interés para empezar."; color: p.muted; Layout.margins: 18 }
            }
        }
    }

    Dialog {
        id: bulk_read_dialog; anchors.centerIn: parent; modal: true
        title: "Marcar todos como leídos"; width: Math.min(460, window.width - 40)
        background: Rectangle { color: p.panel; radius: 10; border.color: p.border }
        header: Label { text: bulk_read_dialog.title; color: p.text; font.bold: true; padding: 16 }
        contentItem: ColumnLayout {
            Label { text: s.read_scope; color: p.accent; font.bold: true; wrapMode: Text.Wrap; Layout.fillWidth: true }
            Label { text: s.read_batch_count + " artículos no leídos. Incluye los artículos almacenados del alcance elegido, también guardados, archivados y descargas, sin limitarse a la búsqueda ni al período del feed."; color: p.text; wrapMode: Text.Wrap; Layout.fillWidth: true }
            Label { text: "Podrás deshacer esta operación. Una nueva operación reemplaza el deshacer anterior."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
            RowLayout {
                Action { text: "Cancelar"; onClicked: bulk_read_dialog.close() }
                Action { text: "Marcar como leídos"; active: true; enabled: s.read_batch_count > 0; onClicked: { backend.mark_all_read(); bulk_read_dialog.close(); } }
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
                    Action { text: "+ Categoría"; active: true; onClicked: {category_dialog.category_index=-1;category_name.text="";category_dialog.open();} }
                }
                RowLayout {
                    Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                    Label { text: "Mostrar artículos de"; color: p.text }
                    SettingsChoice {
                        id: period_selector; objectName: "articlePeriodSelector"
                        property var keys: ["hoy", "semana", "mes", "ano"]
                        model: ["Hoy", "Últimos 7 días", "Últimos 30 días", "Este año"]
                        currentIndex: keys.indexOf(s.article_period)
                        onActivated: backend.set_article_period(keys[currentIndex])
                        Layout.fillWidth: true
                    }
                }
                Label {
                    text: "Se aplica a todas las fuentes. Actualiza el feed después de cambiar el período. Solo se incluyen artículos con fecha disponible en el RSS; guardados, archivados y descargas se conservan."
                    color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                }
                RowLayout {
                    Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                    Label { text: "Conservar historial"; color: p.text }
                    SettingsChoice {
                        property var days: [0, 1, 7, 30, 90, 180, 365]
                        model: ["Sin límite", "1 día", "1 semana", "30 días", "90 días", "180 días", "1 año"]
                        currentIndex: days.indexOf(s.history_days)
                        onActivated: backend.set_history_retention(days[currentIndex])
                        Layout.fillWidth: true
                    }
                }
                Label {
                    text: "Plazo desde la primera recepción. Se protegen los pendientes de lectura, guardados (favoritos), archivados y descargas. La limpieza se realiza al iniciar y actualizar. Puedes recuperar los retirados durante 30 días; los estados de lectura y descarte se conservan."
                    color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                }
                Action { text: "Recuperar historial retirado…"; Layout.leftMargin: 18; onClicked: backend.navigate("retirados", "", "") }
                Repeater { model: s.categories
                    delegate: Rectangle {
                        id: settings_cat; required property var modelData; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; implicitHeight: cat_settings.implicitHeight+20; color: p.panel; border.color: p.border; radius: 6
                        ColumnLayout { id: cat_settings; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10; spacing: 6
                            RowLayout { Layout.fillWidth: true
                                SectionTitle { text: settings_cat.modelData.name; font.pixelSize: 14; Layout.fillWidth: true }
                                Action { text: "↑"; compact: true; onClicked: backend.move_category(settings_cat.modelData.index,-1) }
                                Action { text: "↓"; compact: true; onClicked: backend.move_category(settings_cat.modelData.index,1) }
                                Action { text: "Editar"; compact: true; onClicked: {category_dialog.category_index=settings_cat.modelData.index;category_name.text=settings_cat.modelData.name;category_dialog.open();} }
                                Action { text: "×"; compact: true; onClicked: backend.delete_category(settings_cat.modelData.index) }
                            }
                            Repeater { model: settings_cat.modelData.sources
                                delegate: ColumnLayout { id: source_row; required property var modelData; Layout.fillWidth: true
                                    RowLayout { Layout.fillWidth: true
                                        Image { source: source_row.modelData.icon; visible: source.toString().length>0; Layout.preferredWidth: 16; Layout.preferredHeight: 16; smooth: true; mipmap: true }
                                        Label { text: source_row.modelData.name; color: p.text; Layout.fillWidth: true; wrapMode: Text.Wrap }
                                        Action { text: "Editar"; compact: true; onClicked: source_dialog.edit(settings_cat.modelData.index,source_row.modelData) }
                                        Action { text: "↑"; compact: true; onClicked: backend.move_source(settings_cat.modelData.index,source_row.modelData.index,-1) }
                                        Action { text: "↓"; compact: true; onClicked: backend.move_source(settings_cat.modelData.index,source_row.modelData.index,1) }
                                        Action { text: "×"; compact: true; onClicked: {delete_dialog.cat=settings_cat.modelData.index;delete_dialog.src=source_row.modelData.index;delete_dialog.open();} }
                                    }
                                    Label { text: source_row.modelData.feed || source_row.modelData.url; color: p.muted; font.pixelSize: 10; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                }
                            }
                            Action { text: "+ Añadir fuente"; active: true; onClicked: source_dialog.edit(settings_cat.modelData.index,null) }
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
            Label { text: "Descarga todos los artículos cargados en el feed, con su texto e imagen. Las descargas existentes se conservan."; color: p.text; wrapMode: Text.Wrap; Layout.fillWidth: true }
            Check { id: offline_translation; text: "Incluir traducción al español"; Layout.fillWidth: true }
            Label { text: "Preparar las traducciones requiere conexión y puede tardar. Después podrás leerlas sin internet."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
            RowLayout { Action { text: "Cancelar"; onClicked: bulk_dialog.close() } Action { text: "Modo offline"; active: true; onClicked: {backend.download_all(offline_translation.checked);bulk_dialog.close();} } }
        }
    }
    Dialog {
        id: category_dialog; property int category_index: -1; anchors.centerIn: parent; modal: true; title: category_index<0 ? "Nueva categoría" : "Editar categoría"; width: Math.min(400,window.width-40)
        background: Rectangle { color: p.panel; radius: 10; border.color: p.border }
        contentItem: ColumnLayout {
            Search { id: category_name; placeholderText: "Nombre"; Layout.fillWidth: true }
            RowLayout { Action { text: "Cancelar"; onClicked: category_dialog.close() } Action { text: "Guardar"; active: true; onClicked: {backend.save_category(category_dialog.category_index,category_name.text);category_dialog.close();} } }
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
        header: Label { text: source_dialog.title; color: p.text; padding: 16; font.bold: true }
        contentItem: ScrollView { id: source_editor_scroll; clip: true; contentWidth: availableWidth
            ColumnLayout { width: source_editor_scroll.availableWidth; spacing: 12
                Search { id: src_name; placeholderText: "Nombre de la fuente"; Layout.fillWidth: true }
                Search { id: src_url; placeholderText: "https://sitio.com"; Layout.fillWidth: true }
                Check { id: src_show_shortcut; text: "Mostrar atajo en la barra superior"; Layout.fillWidth: true }
                Check { id: src_shortcut; text: "Solo sitio web (sin cargar artículos)"; Layout.fillWidth: true }
                Search { visible: !src_shortcut.checked; id: src_feed; placeholderText: "URL RSS (opcional, se detecta al actualizar)"; Layout.fillWidth: true }
                ComboBox { id: src_category; model: s.categories; textRole: "name"; Layout.fillWidth: true; implicitHeight: 38
                    background: Rectangle { radius: 8; color: p.hover; border.color: src_category.activeFocus ? p.accent : p.border }
                    contentItem: Text { text: src_category.displayText; color: p.text; leftPadding: 12; rightPadding: 28; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
                    indicator: Text { text: "⌄"; color: p.muted; x: parent.width-width-12; y: (parent.height-height)/2 }
                    delegate: ItemDelegate { required property var modelData; width: src_category.width; text: modelData.name
                        contentItem: Text { text: parent.text; color: p.text; padding: 8 }
                        background: Rectangle { color: parent.hovered ? p.hover : p.panel }
                    }
                    popup: Popup { y: src_category.height+4; width: src_category.width; implicitHeight: Math.min(240, category_choices.contentHeight+8); padding: 4
                        background: Rectangle { color: p.panel; radius: 8; border.color: p.border }
                        contentItem: ListView { id: category_choices; clip: true; model: src_category.popup.visible ? src_category.delegateModel : null; currentIndex: src_category.highlightedIndex }
                    }
                }
                RowLayout { visible: !src_shortcut.checked; Label { text: "Límite por fuente"; color:p.text } SpinBox { id: src_maximum; from:1; to:1000; implicitWidth: 150; implicitHeight: 38
                    background: Rectangle { color: p.hover; radius: 8; border.color: src_maximum.activeFocus ? p.accent : p.border }
                    contentItem: Text { text: src_maximum.value; color: p.text; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    down.indicator: Rectangle { x: 0; width: 36; height: parent.height; radius: 8; color: src_maximum.down.hovered ? p.border : p.hover; Text { anchors.centerIn: parent; text: "−"; color: p.text; font.pixelSize: 20 } }
                    up.indicator: Rectangle { x: parent.width-width; width: 36; height: parent.height; radius: 8; color: src_maximum.up.hovered ? p.border : p.hover; Text { anchors.centerIn: parent; text: "+"; color: p.text; font.pixelSize: 20 } }
                } }
                Switch { visible: !src_shortcut.checked; id: src_translation; text: "Traducir títulos al español"; Layout.fillWidth: true; padding: 10; spacing: 12
                    background: Rectangle { radius: 8; color: p.hover; border.color: src_translation.hovered ? p.accent : p.border }
                    indicator: Rectangle { x: 10; y: (src_translation.height-height)/2; width: 42; height: 24; radius: 12; color: src_translation.checked ? ((s.theme === "gris" || s.theme === "periodico") ? "#62834b" : p.accent) : "#777b82"
                        Rectangle { x: src_translation.checked ? 21 : 3; y: 3; width: 18; height: 18; radius: 9; color: "#ffffff"; Behavior on x { NumberAnimation { duration: 110 } } }
                    }
                    contentItem: Text { text: src_translation.text; color: p.text; leftPadding: 54; verticalAlignment: Text.AlignVCenter }
                }
                RowLayout { Action { text: "Elegir icono"; onClicked: icon_file.open() } Action { text: "Quitar icono"; onClicked: source_dialog.icon_url="" } }
                RowLayout { Action { text: "Cancelar"; onClicked: source_dialog.close() } Action { text: "Guardar"; active:true; onClicked: {if (backend.save_source(source_dialog.category_index,source_dialog.source_index,src_category.currentIndex,src_name.text,src_url.text,src_feed.text,src_maximum.value,src_translation.checked,source_dialog.icon_url,src_shortcut.checked,src_show_shortcut.checked)) source_dialog.close();} } }
            }
        }
    }
    FileDialog { id: icon_file; title: "Icono de la fuente"; nameFilters: ["Imágenes (*.png *.jpg *.jpeg *.webp)"]; onAccepted: source_dialog.icon_url=selectedFile.toString() }

    Dialog {
        id: quote_dialog; objectName: "quote_dialog"; anchors.centerIn: parent; modal: true; title: "Preparar imagen de la cita"; width: Math.min(820,window.width-30); height: Math.min(580,window.height-30)
        palette.windowText: "#252525"
        palette.text: "#252525"
        palette.buttonText: "#252525"
        palette.button: "#cccccc"
        palette.base: "#ffffff"
        palette.highlight: "#62834b"
        palette.highlightedText: "#ffffff"
        property bool spanish: false; property bool include_image: false; property int color_index: 0
        function regenerate() {quote_delay.restart();}
        onOpened: {spanish=s.quote_is_translated;include_image=false;color_index=Math.max(0,s.themes.findIndex(t=>t.key===s.theme));regenerate();}
        background: Rectangle { color: "#dedede"; radius: 12; border.color: "#b4b4b4" }
        header: Label { text: quote_dialog.title; padding: 18; color: "#252525"; font.bold: true; font.pixelSize: 17 }
        contentItem: RowLayout {
            spacing: 18
            ColumnLayout { Layout.preferredWidth: 210; Layout.alignment: Qt.AlignTop; spacing: 14
                Button { text: quote_dialog.spanish ? "Mostrar idioma original" : "Mostrar traducción"; enabled: !s.quote_is_translated; onClicked: {quote_dialog.spanish=!quote_dialog.spanish;quote_dialog.regenerate();}
                    background: Rectangle { color: parent.hovered?"#c2c2c2":"#cccccc"; radius:6 } contentItem: Text { text:parent.text;color:"#252525";padding:10;wrapMode:Text.Wrap } Layout.fillWidth:true
                }
                CheckBox {
                    id: quote_image_check; text: "Incluir imagen del artículo"
                    Layout.fillWidth: true; spacing: 8
                    enabled: s.quote_has_image; checked: quote_dialog.include_image
                    onClicked: {quote_dialog.include_image=checked;quote_dialog.regenerate();}
                    contentItem: Text {
                        text: quote_image_check.text; color: quote_image_check.enabled ? "#252525" : "#686868"
                        leftPadding: quote_image_check.indicator.width + quote_image_check.spacing
                        wrapMode: Text.Wrap; verticalAlignment: Text.AlignVCenter
                    }
                    indicator: Rectangle {
                        width: 20; height: 20; y: (quote_image_check.height-height)/2; radius: 4
                        color: quote_image_check.checked ? "#62834b" : "#eeeeee"; border.color: "#686868"
                        Text { anchors.centerIn: parent; text: quote_image_check.checked ? "✓" : ""; color: "#ffffff" }
                    }
                }
                Button { text:"Color " + s.themes[quote_dialog.color_index].name; Layout.fillWidth:true; onClicked:{quote_dialog.color_index=(quote_dialog.color_index+1)%s.themes.length;quote_dialog.regenerate();}
                    background:Rectangle { color:s.themes[quote_dialog.color_index].key==="periodico"?"#e6e6e6":"#232a34";radius:6 }
                    contentItem:Text {text:parent.text;color:s.themes[quote_dialog.color_index].color;wrapMode:Text.Wrap;padding:10}
                }
                Label { text:s.quote_busy?"Actualizando vista previa…":s.quote_is_translated?"Para citar el original exacto, selecciona el texto en Ver original.":"Vista previa · PNG o JPG"; color:"#555555"; wrapMode:Text.Wrap; Layout.fillWidth:true }
            }
            Image { source:s.quote_preview; Layout.fillWidth:true; Layout.fillHeight:true; fillMode:Image.PreserveAspectFit; smooth:true; mipmap:true; cache:false }
        }
        footer: RowLayout { Item {Layout.fillWidth:true} Button {text:"Cancelar";onClicked:quote_dialog.close()} Button {text:"Guardar imagen…";enabled:s.quote_can_save;onClicked:quote_file.open()} Item {width:12} }
        Timer { id:quote_delay;interval:150;onTriggered:backend.update_quote(quote_dialog.spanish,quote_dialog.include_image,s.themes[quote_dialog.color_index].key) }
    }
    FileDialog { id:quote_file;title:"Guardar cita";fileMode:FileDialog.SaveFile;currentFolder:s.downloads_folder;nameFilters:["Imagen PNG (*.png)","Imagen JPG (*.jpg *.jpeg)"];defaultSuffix:selectedNameFilter.index===1?"jpg":"png";onAccepted:backend.export_quote(selectedFile.toString()) }
    Dialog { id:error_dialog;anchors.centerIn:parent;modal:true;title:"Choroy Reader";standardButtons:Dialog.Ok;width:Math.min(480,window.width-40)
        property string message:""
        Label {text:error_dialog.message;wrapMode:Text.Wrap;width:parent.width;color:p.text}
        background:Rectangle {color:p.panel;radius:8;border.color:p.border}
    }
    Connections {target:backend;function onError(message){error_dialog.message=message;error_dialog.open();}}
}
