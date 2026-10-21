import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Compact preset palette with an optional exact HEX input.
RowLayout {
    id: picker
    property alias text: hexInput.text
    property string placeholderText: "#79b7e8"
    property var colors: ["#192535", "#25364a", "#ecf2fb", "#79b7e8", "#55c5ad", "#f2bc73", "#ec839c", "#a38bff"]
    spacing: 8
    Row {
        spacing: 6
        Repeater {
            model: picker.colors
            delegate: Rectangle {
                required property string modelData
                width: 26
                height: 26
                radius: 8
                color: modelData
                border.width: picker.text.toLowerCase() === modelData.toLowerCase() ? 3 : 1
                border.color: picker.text.toLowerCase() === modelData.toLowerCase() ? "#ffffff" : "#54667c"
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: hexInput.text = modelData
                }
            }
        }
    }
    TextField {
        id: hexInput
        Layout.fillWidth: true
        Layout.minimumWidth: 96
        Layout.preferredWidth: 120
        implicitHeight: 34
        placeholderText: picker.placeholderText
        color: "#f0f5ff"
        placeholderTextColor: "#8298b4"
        selectByMouse: true
        font.pixelSize: 12
        background: Rectangle {
            color: "#223146"
            radius: 8
            border.color: hexInput.activeFocus ? "#6fc4ff" : "#3a4d63"
        }
    }
}
