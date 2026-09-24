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
    title: "MinimalFeed"
    property var s: backend.state
    property var p: s.palette
    property real feedScroll: 0
    property var expandedCategories: ({})
    color: p.bg
    font.family: "Sans Serif"
    font.pixelSize: 13

    component Action: Button {
        id: control
        property bool active: false
        property bool compact: false
        leftPadding: 12; rightPadding: 12; topPadding: compact ? 5 : 9; bottomPadding: compact ? 5 : 9
        implicitHeight: Math.max(32, contentItem.implicitHeight + topPadding + bottomPadding)
        background: Rectangle { radius: 6; color: control.active || control.down ? p.hover : control.hovered ? p.hover : "transparent"; border.color: control.visualFocus ? p.accent : "transparent" }
        contentItem: Text { text: control.text; color: !control.enabled ? p.muted : control.active ? p.accent : p.text; font: control.font; wrapMode: Text.Wrap; verticalAlignment: Text.AlignVCenter }
    }
    component Search: TextField {
        id: field
        implicitHeight: 38
        leftPadding: 14; rightPadding: 14
        color: p.text; placeholderTextColor: p.muted; selectionColor: p.accent; selectedTextColor: p.accentText
        background: Rectangle { color: p.hover; radius: 18; border.width: 1; border.color: field.activeFocus ? p.accent : p.border }
    }
    component Check: CheckBox {
        id: check
        spacing: 10
        contentItem: Text { text: check.text; color: p.text; leftPadding: check.indicator.width + check.spacing; verticalAlignment: Text.AlignVCenter; wrapMode: Text.Wrap }
        indicator: Rectangle { x: 0; y: (check.height-height)/2; width: 20; height: 20; radius: 5; color: check.checked ? p.accent : p.hover; border.color: p.border
            Text { anchors.centerIn: parent; text: check.checked ? "✓" : ""; color: p.accentText }
        }
    }
    component Glyph: Item {
        id: glyph
        property string kind: "save"
        property color ink: p.accent
        property bool filled: false
        implicitWidth: 20; implicitHeight: 20
        onInkChanged: drawing.requestPaint()
        onFilledChanged: drawing.requestPaint()
        Canvas { id: drawing; anchors.fill: parent; antialiasing: true
            onPaint: {
                const c = getContext("2d"); c.reset(); c.scale(width/24,height/24); c.strokeStyle=glyph.ink; c.fillStyle=glyph.ink; c.lineWidth=1.7; c.lineJoin="round"; c.lineCap="round";
                c.beginPath();
                if (glyph.kind === "save") { c.moveTo(6,3);c.lineTo(18,3);c.lineTo(18,21);c.lineTo(12,16);c.lineTo(6,21);c.closePath(); if(glyph.filled)c.fill();c.stroke(); }
                else { c.moveTo(12,3);c.lineTo(12,15);c.moveTo(7,10);c.lineTo(12,15);c.lineTo(17,10);c.moveTo(4,16);c.lineTo(4,21);c.lineTo(20,21);c.lineTo(20,16);c.stroke();if(glyph.filled){c.beginPath();c.arc(20,4,3,0,Math.PI*2);c.fill();} }
            }
        }
    }
    component IconAction: Button {
        id: iconControl
        property string kind: "save"
        property bool filled: false
        property string hint: ""
        implicitWidth: 34; implicitHeight: 34; padding: 7
        Accessible.name: hint
        background: Rectangle { radius: 6; color: iconControl.hovered ? p.hover : p.card; border.color: iconControl.visualFocus ? p.accent : p.border }
        contentItem: Glyph { kind: iconControl.kind; filled: iconControl.filled; opacity: iconControl.enabled ? 1 : 0.4 }
        ToolTip.visible: hovered; ToolTip.text: hint; ToolTip.delay: 400
    }
    component SectionTitle: Label { color: p.text; font.pixelSize: 17; font.bold: true; wrapMode: Text.Wrap }

    ColumnLayout {
        anchors.fill: parent; spacing: 0
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 84; color: p.bg
            RowLayout {
                anchors.fill: parent; anchors.margins: 10; spacing: 14
                Image { objectName: "appLogo"; source: s.logo; Layout.preferredWidth: 64; Layout.preferredHeight: 64; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true }
                ColumnLayout {
                    Layout.fillWidth: true
                    Label { text: "Tus fuentes. Tu feed. Sin distracciones."; color: p.accent; font.bold: true; font.pixelSize: 15; Layout.alignment: Qt.AlignHCenter; wrapMode: Text.Wrap; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
                    Rectangle { Layout.preferredWidth: 100; Layout.preferredHeight: 2; color: p.accent; Layout.alignment: Qt.AlignHCenter }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
            Rectangle {
                Layout.preferredWidth: 280; Layout.fillHeight: true; color: p.panel
                ColumnLayout {
                    anchors.fill: parent; spacing: 2
                    ColumnLayout {
                        Layout.fillWidth: true; Layout.margins: 12; spacing: 1
                        Action { text: s.busy ? "Actualizando…" : "Actualizar feed"; enabled: !s.busy; Layout.fillWidth: true; onClicked: backend.refresh() }
                        Action { text: "Feed"; active: s.page === "feed"; Layout.fillWidth: true; onClicked: backend.navigate("feed", "", "") }
                        Action { text: "Diseño"; active: s.page === "design"; Layout.fillWidth: true; onClicked: backend.navigate("design", "", "") }
                        Action { text: "Fuentes/Categorías"; active: s.page === "sources"; Layout.fillWidth: true; onClicked: backend.navigate("sources", "", "") }
                        Action { text: "Radar"; active: s.page === "radar"; Layout.fillWidth: true; onClicked: backend.navigate("radar", "", "") }
                    }
                    Rectangle { Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22; height: 1; color: p.border }
                    ScrollView {
                        id: sideScroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                        contentWidth: availableWidth
                        ColumnLayout {
                            width: sideScroll.availableWidth; spacing: 4
                            Action { text: "≡  Todo el feed"; active: s.page === "feed" && s.category === ""; Layout.fillWidth: true; Layout.margins: 8; onClicked: backend.navigate("feed", "", "") }
                            Action { text: "◇  Guardados"; active: s.page === "guardados"; Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; onClicked: backend.navigate("guardados", "", "") }
                            Action { text: "↓  Descargas"; active: s.page === "descargas"; Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; onClicked: backend.navigate("descargas", "", "") }
                            RowLayout {
                                Layout.fillWidth: true; Layout.margins: 18
                                Label { text: "Radar de intereses"; color: p.text; Layout.fillWidth: true }
                                Switch {
                                    id: radarSwitch; objectName: "radarSwitch"; checked: s.radar; onClicked: backend.toggleRadar(); padding: 0
                                    indicator: Rectangle { width: 42; height: 24; radius: 12; color: radarSwitch.checked ? p.accent : "#777b82"
                                        Rectangle { x: radarSwitch.checked ? 21 : 3; y: 3; width: 18; height: 18; radius: 9; color: "#f0f0f0"; Behavior on x { NumberAnimation { duration: 110 } } }
                                    }
                                }
                            }
                            Label { text: "TUS CATEGORÍAS"; color: p.muted; font.pixelSize: 10; font.bold: true; Layout.leftMargin: 22; Layout.bottomMargin: 5 }
                            Repeater {
                                model: s.categories
                                delegate: ColumnLayout {
                                    id: categoryDelegate; required property var modelData
                                    property bool expanded: !!window.expandedCategories[modelData.name]
                                    Layout.fillWidth: true; spacing: 2
                                    Action { text: (categoryDelegate.expanded ? "⌄  " : "›  ") + categoryDelegate.modelData.name + "  ·  " + categoryDelegate.modelData.sources.length; active: s.category === categoryDelegate.modelData.name; Layout.fillWidth: true; Layout.leftMargin: 12; Layout.rightMargin: 12; onClicked: {const next=Object.assign({},window.expandedCategories);next[categoryDelegate.modelData.name]=!categoryDelegate.expanded;window.expandedCategories=next;} }
                                    ColumnLayout {
                                        visible: categoryDelegate.expanded; Layout.fillWidth: true; Layout.leftMargin: 28; Layout.rightMargin: 12; spacing: 1
                                        Action { text: "Todas las fuentes"; compact: true; Layout.fillWidth: true; onClicked: backend.navigate("feed",categoryDelegate.modelData.name,"") }
                                        Repeater { model: categoryDelegate.modelData.sources
                                            delegate: Action { required property var modelData; text: modelData.name; compact: true; active: s.source === modelData.url; Layout.fillWidth: true; onClicked: backend.navigate("feed",categoryDelegate.modelData.name,modelData.url) }
                                        }
                                    }
                                }
                            }
                            Item { height: 12; Layout.fillWidth: true }
                        }
                    }
                    Rectangle { Layout.fillWidth: true; Layout.margins: 18; height: 1; color: p.border }
                    Label { text: s.radarBusy ? "Radar: analizando contenido…" : s.status; color: p.muted; wrapMode: Text.Wrap; font.pixelSize: 10; Layout.fillWidth: true; Layout.margins: 18 }
                }
            }
            Loader {
                id: mainLoader; Layout.fillWidth: true; Layout.fillHeight: true
                sourceComponent: s.reader.link ? readerPage : s.page === "design" ? designPage : s.page === "radar" ? radarPage : s.page === "sources" ? sourcesPage : feedPage
            }
        }
    }

    Component {
        id: feedPage
        ColumnLayout {
            spacing: 8
            Search { objectName: "titleSearch"; Layout.fillWidth: true; Layout.margins: 14; placeholderText: "Buscar en títulos"; text: s.query; onTextEdited: titleSearchDelay.restart()
                Timer { id: titleSearchDelay; interval: 180; onTriggered: backend.searchTitles(parent.text) }
            }
            Label { text: s.page === "descargas" ? "Descargas · Sin conexión" : s.page === "guardados" ? "Guardados" : s.category; visible: text.length > 0; color: p.accent; font.bold: true; Layout.leftMargin: 18 }
            Action {text: "Abrir sitio de la fuente ↗"; visible:s.source.length>0; Layout.leftMargin:18; compact:true; onClicked:backend.openUrl(s.source)}
            ScrollView {
                id: feedScrollView; Component.onCompleted: Qt.callLater(function(){feedScrollView.contentItem.contentY=window.feedScroll;}); Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth
                ColumnLayout {
                    width: feedScrollView.availableWidth; spacing: 10
                    Label { text: s.busy ? "Cargando artículos e imágenes…" : s.query ? "No hay títulos que coincidan." : "No hay artículos en esta sección."; visible: s.articles.length === 0; color: p.muted; Layout.fillWidth: true; Layout.margins: 20; wrapMode: Text.Wrap }
                    GridLayout {
                        id: cardsGrid; Layout.fillWidth: true; Layout.margins: 12; columns: Math.max(1,Math.min(s.columns,Math.floor((feedScrollView.availableWidth-24)/210))); columnSpacing: 8; rowSpacing: 8
                        Repeater {
                            model: s.articles
                            delegate: Rectangle {
                                id: card; required property var modelData
                                Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.alignment: Qt.AlignTop
                                implicitHeight: cardBody.implicitHeight + 2; color: p.card; radius: 2
                                border.color: cardHover.hovered ? p.accent : p.border; border.width: 1
                                HoverHandler { id: cardHover }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: {window.feedScroll=feedScrollView.contentItem.contentY;backend.openArticle(card.modelData.link);} }
                                ColumnLayout {
                                    id: cardBody; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 1; spacing: 0
                                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: cardsGrid.columns === 1 ? 200 : 150; color: p.hover; clip: true
                                        Image { anchors.fill: parent; source: card.modelData.image; fillMode: Image.PreserveAspectCrop; asynchronous: true; smooth: true; mipmap: true }
                                        Label { anchors.centerIn: parent; visible: card.modelData.image === ""; text: "Imagen no disponible"; color: p.muted; font.pixelSize: 11 }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true; Layout.margins: 12; spacing: 8
                                        Label { visible: card.modelData.radar > 0; text: "◎ ".repeat(card.modelData.radar) + " Radar · " + card.modelData.interests + " intereses"; color: p.accent; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.Wrap }
                                        RowLayout { Layout.fillWidth: true
                                            Label { text: card.modelData.source; color: p.accent; font.bold: true; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                                            Label { text: card.modelData.date; color: p.muted; font.pixelSize: 10 }
                                        }
                                        Text { text: card.modelData.titleHtml; textFormat: Text.RichText; color: card.modelData.seen ? p.muted : p.text; font.pixelSize: cardsGrid.columns === 1 ? 15 : 13; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                        RowLayout { visible: card.modelData.showTranslation && card.modelData.translation.length > 0; Layout.fillWidth: true; spacing: 6
                                            Rectangle { width: 16; height: 16; radius: 8; color: "#c9293b"; Layout.alignment: Qt.AlignTop
                                                Rectangle { anchors.centerIn: parent; width: 15; height: 7; radius: 1; color: "#f6c645" }
                                            }
                                            Text { text: card.modelData.translationHtml; textFormat: Text.RichText; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 13 }
                                        }
                                        RowLayout {
                                            IconAction { kind: "save"; filled: card.modelData.saved; hint: filled ? "Quitar guardado" : "Guardar artículo"; onClicked: backend.toggleSaved(card.modelData.link) }
                                            IconAction { kind: "download"; filled: card.modelData.downloaded; enabled: !card.modelData.downloading; hint: filled ? "Eliminar descarga" : "Descargar para leer sin conexión"; onClicked: backend.toggleDownload(card.modelData.link) }
                                            Item { Layout.fillWidth: true }
                                        }
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
        id: readerPage
        ScrollView {
            id: readerScroll; objectName: "readerPage"; clip: true; contentWidth: availableWidth
            property bool marking: false
            property string markerColor: p.light ? "#ffe88f" : p.accent
            property int markAnchor: 0
            property int menuPosition: 0
            property string selectedQuote: ""
            ColumnLayout {
                width: readerScroll.availableWidth; spacing: 12
                Action { text: "← Volver al feed"; Layout.leftMargin: 16; Layout.topMargin: 12; onClicked: backend.closeArticle() }
                RowLayout { Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18
                    Search { id: bodySearch; objectName: "bodySearch"; placeholderText: "Buscar en artículo"; Layout.fillWidth: true; Layout.minimumWidth: 80; onTextEdited: backend.searchDocument(text); onAccepted: backend.nextMatch() }
                    Action { text: s.reader.translating ? "Traduciendo…" : s.reader.translated ? "Ver original" : "Leer en español"; active: true; enabled: s.reader.ready && !s.reader.translating; onClicked: backend.translateArticle() }
                    Action { text: "Abrir original ↗"; onClicked: backend.openUrl(s.reader.link) }
                }
                Image { source: s.reader.image || ""; visible: s.reader.showImage && source.toString().length > 0; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; Layout.preferredHeight: visible ? Math.min(280,width*9/16) : 0; fillMode: Image.PreserveAspectCrop; clip: true; smooth: true; mipmap: true }
                RowLayout { Layout.leftMargin: 18
                    IconAction { kind: "save"; filled: !!s.reader.saved; hint: filled ? "Quitar guardado" : "Guardar"; onClicked: backend.toggleSaved(s.reader.link) }
                    IconAction { kind: "download"; filled: !!s.reader.downloaded; enabled: !s.reader.downloading; hint: filled ? "Eliminar descarga" : "Descargar"; onClicked: backend.toggleDownload(s.reader.link) }
                }
                SectionTitle { text: s.reader.title || ""; font.pixelSize: 23; Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22 }
                Label { text: (readerScroll.marking ? "Destacador activo · Arrastra para marcar. " : "") + (s.reader.status || ""); color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22 }
                TextEdit {
                    id: articleText; objectName: "articleText"; Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22; Layout.bottomMargin: 28
                    text: s.reader.body || ""; textFormat: TextEdit.PlainText; readOnly: true; selectByMouse: !readerScroll.marking; persistentSelection: true
                    wrapMode: TextEdit.Wrap; color: p.text; font.pixelSize: 16; selectionColor: p.accent; selectedTextColor: p.accentText
                    property string attachedText: ""
                    onTextChanged: {
                        if (text !== attachedText) {
                            attachedText = text;
                            Qt.callLater(function(){backend.attachDocument(articleText.textDocument); bodySearch.text="";});
                        }
                    }
                    Component.onCompleted: backend.attachDocument(textDocument)
                    MouseArea {
                        anchors.fill: parent; enabled: readerScroll.marking; acceptedButtons: Qt.LeftButton; cursorShape: Qt.PointingHandCursor
                        onPressed: function(mouse){ readerScroll.markAnchor = articleText.positionAt(mouse.x,mouse.y); articleText.deselect(); }
                        onPositionChanged: function(mouse){ if(pressed) backend.mark(readerScroll.markAnchor,articleText.positionAt(mouse.x,mouse.y),readerScroll.markerColor); }
                        onReleased: function(mouse){ backend.mark(readerScroll.markAnchor,articleText.positionAt(mouse.x,mouse.y),readerScroll.markerColor); }
                    }
                    MouseArea {
                        anchors.fill: parent; acceptedButtons: Qt.RightButton
                        onClicked: function(mouse){readerScroll.menuPosition=articleText.positionAt(mouse.x,mouse.y);readerScroll.selectedQuote=articleText.selectedText;articleMenu.popup();}
                    }
                    Menu {
                        id: articleMenu
                        MenuItem { text: "Crear imagen de la cita…"; enabled: readerScroll.selectedQuote.length > 0; onTriggered: {backend.prepareQuote(readerScroll.selectedQuote);if(readerScroll.selectedQuote.length<=500)quoteDialog.open();} }
                        Menu {
                            title: "Destacador"
                            Repeater { model: s.themes
                                delegate: MenuItem { required property var modelData; visible: modelData.key !== "periodico"; text: "●  " + modelData.name
                                    contentItem: Text { text: parent.text; color: modelData.color; font.pixelSize: 13; padding: 5 }
                                    onTriggered: {readerScroll.markerColor=modelData.color;readerScroll.marking=true;articleText.deselect();}
                                }
                            }
                            MenuItem { text: "Destacar selección"; enabled: articleText.selectionEnd > articleText.selectionStart; onTriggered: backend.mark(articleText.selectionStart,articleText.selectionEnd,readerScroll.markerColor) }
                            MenuSeparator {}
                            MenuItem { text: "Desactivar destacador"; onTriggered: readerScroll.marking=false }
                        }
                        MenuItem { text: "Quitar destacado"; onTriggered: {if(articleText.selectionEnd>articleText.selectionStart)backend.mark(articleText.selectionStart,articleText.selectionEnd,"");else backend.removeMarkAt(readerScroll.menuPosition);} }
                    }
                }
            }
            Connections {
                target: backend
                function onDocumentSearch(position,count) {
                    if(position>=0){const r=articleText.positionToRectangle(position);readerScroll.contentItem.contentY=Math.max(0,articleText.y+r.y-60);}
                    searchCount.text = bodySearch.text.length ? count + " coincidencias" : "";
                }
            }
            Label { id: searchCount; color: p.muted; font.pixelSize: 10; anchors.right: parent.right; anchors.top: parent.top }
        }
    }

    Component {
        id: designPage
        ScrollView { id: designScroll; clip: true; contentWidth: availableWidth
            ColumnLayout { width: designScroll.availableWidth; spacing: 16
                SectionTitle { text: "Diseño"; Layout.margins: 18 }
                Check { text: "Mostrar imágenes dentro de los artículos"; checked: s.showImages; Layout.leftMargin: 18; onClicked: backend.setDesign(s.columns,checked,s.translateTitles) }
                Check { text: "Mostrar traducción de los títulos"; checked: s.translateTitles; Layout.leftMargin: 18; onClicked: backend.setDesign(s.columns,s.showImages,checked) }
                RowLayout { Layout.leftMargin: 18
                    Label { text: "Artículos por fila (máximo)"; color: p.text }
                    SpinBox { from: 1; to: 5; value: s.columns; onValueModified: backend.setDesign(value,s.showImages,s.translateTitles) }
                }
                SectionTitle { text: "Tema"; Layout.leftMargin: 18 }
                Flow { Layout.fillWidth: true; Layout.margins: 18; spacing: 8
                    Repeater { model: s.themes
                        delegate: Button { required property var modelData; text: modelData.name; onClicked: backend.setTheme(modelData.key); padding: 12
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
        id: radarPage
        ColumnLayout { anchors.margins: 18; spacing: 14
            SectionTitle { text: "Radar de intereses"; Layout.margins: 18 }
            Label { text: "Palabras o frases separadas por comas"; color: p.text; Layout.leftMargin: 18 }
            Search { id: radarWords; text: s.radarWords; placeholderText: "privacidad, seguridad, inteligencia artificial"; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18 }
            Action { text: "Guardar intereses"; active: true; Layout.leftMargin: 18; onClicked: backend.saveRadar(radarWords.text) }
            Label { text: "El radar analiza títulos y contenido. Prioriza los intereses distintos y después el número de menciones.\n\n◎ Un interés · ◎◎ Dos · ◎◎◎ Tres o más\n\nActívalo con el switch sobre las fuentes."; color: p.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.margins: 18 }
            Item { Layout.fillHeight: true }
        }
    }
    Component {
        id: sourcesPage
        ScrollView { id: sourcesScroll; clip: true; contentWidth: availableWidth
            ColumnLayout { width: sourcesScroll.availableWidth; spacing: 10
                RowLayout { Layout.fillWidth: true; Layout.margins: 18
                    SectionTitle { text: "Fuentes y categorías"; Layout.fillWidth: true }
                    Action { text: "+ Categoría"; active: true; onClicked: {categoryDialog.categoryIndex=-1;categoryName.text="";categoryDialog.open();} }
                }
                Repeater { model: s.categories
                    delegate: Rectangle {
                        id: settingsCat; required property var modelData; Layout.fillWidth: true; Layout.leftMargin: 18; Layout.rightMargin: 18; implicitHeight: catSettings.implicitHeight+20; color: p.panel; border.color: p.border; radius: 6
                        ColumnLayout { id: catSettings; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10; spacing: 6
                            RowLayout { Layout.fillWidth: true
                                SectionTitle { text: settingsCat.modelData.name; font.pixelSize: 14; Layout.fillWidth: true }
                                Action { text: "↑"; compact: true; onClicked: backend.moveCategory(settingsCat.modelData.index,-1) }
                                Action { text: "↓"; compact: true; onClicked: backend.moveCategory(settingsCat.modelData.index,1) }
                                Action { text: "Editar"; compact: true; onClicked: {categoryDialog.categoryIndex=settingsCat.modelData.index;categoryName.text=settingsCat.modelData.name;categoryDialog.open();} }
                                Action { text: "×"; compact: true; onClicked: backend.deleteCategory(settingsCat.modelData.index) }
                            }
                            Repeater { model: settingsCat.modelData.sources
                                delegate: ColumnLayout { id: sourceRow; required property var modelData; Layout.fillWidth: true
                                    RowLayout { Layout.fillWidth: true
                                        Image { source: sourceRow.modelData.icon; visible: source.toString().length>0; Layout.preferredWidth: 16; Layout.preferredHeight: 16; smooth: true; mipmap: true }
                                        Label { text: sourceRow.modelData.name; color: p.text; Layout.fillWidth: true; wrapMode: Text.Wrap }
                                        Action { text: "Editar"; compact: true; onClicked: sourceDialog.edit(settingsCat.modelData.index,sourceRow.modelData) }
                                        Action { text: "↑"; compact: true; onClicked: backend.moveSource(settingsCat.modelData.index,sourceRow.modelData.index,-1) }
                                        Action { text: "↓"; compact: true; onClicked: backend.moveSource(settingsCat.modelData.index,sourceRow.modelData.index,1) }
                                        Action { text: "×"; compact: true; onClicked: {deleteDialog.cat=settingsCat.modelData.index;deleteDialog.src=sourceRow.modelData.index;deleteDialog.open();} }
                                    }
                                    Label { text: sourceRow.modelData.feed || sourceRow.modelData.url; color: p.muted; font.pixelSize: 10; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                }
                            }
                            Action { text: "+ Añadir fuente"; active: true; onClicked: sourceDialog.edit(settingsCat.modelData.index,null) }
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: categoryDialog; property int categoryIndex: -1; anchors.centerIn: parent; modal: true; title: categoryIndex<0 ? "Nueva categoría" : "Editar categoría"; width: Math.min(400,window.width-40)
        background: Rectangle { color: p.panel; radius: 10; border.color: p.border }
        contentItem: ColumnLayout {
            Search { id: categoryName; placeholderText: "Nombre"; Layout.fillWidth: true }
            RowLayout { Action { text: "Cancelar"; onClicked: categoryDialog.close() } Action { text: "Guardar"; active: true; onClicked: {backend.saveCategory(categoryDialog.categoryIndex,categoryName.text);categoryDialog.close();} } }
        }
    }
    Dialog {
        id: deleteDialog; property int cat: -1; property int src: -1; anchors.centerIn: parent; modal: true; title: "¿Eliminar esta fuente?"
        standardButtons: Dialog.Yes | Dialog.Cancel; onAccepted: backend.deleteSource(cat,src)
    }
    Dialog {
        id: sourceDialog; anchors.centerIn: parent; modal: true; width: Math.min(520,window.width-40); height: Math.min(640,window.height-40); title: "Fuente"
        property int categoryIndex: -1; property int sourceIndex: -1; property string iconUrl: ""
        function edit(ci,src) { categoryIndex=ci;sourceIndex=src?src.index:-1;srcName.text=src?src.name:"";srcUrl.text=src?src.url:"";srcFeed.text=src?src.feed:"";srcMaximum.value=src?src.maximum:3;srcTranslation.checked=src?src.translate:true;srcCategory.currentIndex=ci;iconUrl=src?src.icon:"";open(); }
        background: Rectangle { color: p.panel; radius: 10; border.color: p.border }
        contentItem: ScrollView { clip: true
            ColumnLayout { width: parent.availableWidth; spacing: 12
                Search { id: srcName; placeholderText: "Nombre de la fuente"; Layout.fillWidth: true }
                Search { id: srcUrl; placeholderText: "https://sitio.com"; Layout.fillWidth: true }
                Search { id: srcFeed; placeholderText: "URL RSS (opcional, se detecta al actualizar)"; Layout.fillWidth: true }
                ComboBox { id: srcCategory; model: s.categories; textRole: "name"; Layout.fillWidth: true }
                RowLayout { Label { text: "Artículos"; color:p.text } SpinBox { id: srcMaximum; from:1; to:100 } }
                Check { id: srcTranslation; text: "Traducir títulos al español" }
                RowLayout { Action { text: "Elegir icono"; onClicked: iconFile.open() } Action { text: "Quitar icono"; onClicked: sourceDialog.iconUrl="" } }
                RowLayout { Action { text: "Cancelar"; onClicked: sourceDialog.close() } Action { text: "Guardar"; active:true; onClicked: {backend.saveSource(sourceDialog.categoryIndex,sourceDialog.sourceIndex,srcCategory.currentIndex,srcName.text,srcUrl.text,srcFeed.text,srcMaximum.value,srcTranslation.checked,sourceDialog.iconUrl);sourceDialog.close();} } }
            }
        }
    }
    FileDialog { id: iconFile; title: "Icono de la fuente"; nameFilters: ["Imágenes (*.png *.jpg *.jpeg *.webp)"]; onAccepted: sourceDialog.iconUrl=selectedFile.toString() }

    Dialog {
        id: quoteDialog; objectName: "quoteDialog"; anchors.centerIn: parent; modal: true; title: "Preparar imagen de la cita"; width: Math.min(820,window.width-30); height: Math.min(580,window.height-30)
        property bool spanish: false; property bool includeImage: false; property int colorIndex: 0
        function regenerate() {quoteDelay.restart();}
        onOpened: {spanish=s.quoteIsTranslated;includeImage=false;colorIndex=Math.max(0,s.themes.findIndex(t=>t.key===s.theme));regenerate();}
        background: Rectangle { color: "#dedede"; radius: 12; border.color: "#b4b4b4" }
        header: Label { text: quoteDialog.title; padding: 18; color: "#252525"; font.bold: true; font.pixelSize: 17 }
        contentItem: RowLayout {
            spacing: 18
            ColumnLayout { Layout.preferredWidth: 210; Layout.alignment: Qt.AlignTop; spacing: 14
                Button { text: quoteDialog.spanish ? "Mostrar idioma original" : "Mostrar traducción"; enabled: !s.quoteIsTranslated; onClicked: {quoteDialog.spanish=!quoteDialog.spanish;quoteDialog.regenerate();}
                    background: Rectangle { color: parent.hovered?"#c2c2c2":"#cccccc"; radius:6 } contentItem: Text { text:parent.text;color:"#252525";padding:10;wrapMode:Text.Wrap } Layout.fillWidth:true
                }
                CheckBox { text:"Incluir imagen del artículo"; enabled:s.quoteHasImage; checked:quoteDialog.includeImage; onClicked:{quoteDialog.includeImage=checked;quoteDialog.regenerate();} }
                Button { text:"Color " + s.themes[quoteDialog.colorIndex].name; Layout.fillWidth:true; onClicked:{quoteDialog.colorIndex=(quoteDialog.colorIndex+1)%s.themes.length;quoteDialog.regenerate();}
                    background:Rectangle { color:s.themes[quoteDialog.colorIndex].key==="periodico"?"#e6e6e6":"#232a34";radius:6 }
                    contentItem:Text {text:parent.text;color:s.themes[quoteDialog.colorIndex].color;wrapMode:Text.Wrap;padding:10}
                }
                Label { text:s.quoteBusy?"Actualizando vista previa…":s.quoteIsTranslated?"Para citar el original exacto, selecciona el texto en Ver original.":"Vista previa · PNG o JPG"; color:"#555555"; wrapMode:Text.Wrap; Layout.fillWidth:true }
            }
            Image { source:s.quotePreview; Layout.fillWidth:true; Layout.fillHeight:true; fillMode:Image.PreserveAspectFit; smooth:true; mipmap:true; cache:false }
        }
        footer: RowLayout { Item {Layout.fillWidth:true} Button {text:"Cancelar";onClicked:quoteDialog.close()} Button {text:"Guardar imagen…";enabled:s.quoteCanSave;onClicked:quoteFile.open()} Item {width:12} }
        Timer { id:quoteDelay;interval:150;onTriggered:backend.updateQuote(quoteDialog.spanish,quoteDialog.includeImage,s.themes[quoteDialog.colorIndex].key) }
    }
    FileDialog { id:quoteFile;title:"Guardar cita";fileMode:FileDialog.SaveFile;currentFolder:s.downloadsFolder;nameFilters:["Imagen PNG (*.png)","Imagen JPG (*.jpg *.jpeg)"];defaultSuffix:selectedNameFilter.index===1?"jpg":"png";onAccepted:backend.exportQuote(selectedFile.toString()) }
    Dialog { id:errorDialog;anchors.centerIn:parent;modal:true;title:"MinimalFeed";standardButtons:Dialog.Ok;width:Math.min(480,window.width-40)
        property string message:""
        Label {text:errorDialog.message;wrapMode:Text.Wrap;width:parent.width;color:p.text}
        background:Rectangle {color:p.panel;radius:8;border.color:p.border}
    }
    Connections {target:backend;function onError(message){errorDialog.message=message;errorDialog.open();}}
}
