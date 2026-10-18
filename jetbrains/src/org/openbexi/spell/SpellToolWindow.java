// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.google.gson.JsonObject;
import com.intellij.openapi.Disposable;
import com.intellij.openapi.actionSystem.*;
import com.intellij.openapi.fileEditor.OpenFileDescriptor;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.wm.*;
import com.intellij.ui.JBColor;
import com.intellij.ui.components.*;
import com.intellij.ui.content.ContentFactory;
import com.intellij.ui.table.JBTable;
import com.intellij.util.ui.JBUI;
import java.awt.*;
import java.awt.event.*;
import java.time.*;
import java.time.format.DateTimeFormatter;
import javax.swing.*;
import javax.swing.table.*;

/** Theme-aware procedure workspace following SPELL GUI manual sections 3 and 5. */
public final class SpellToolWindow implements ToolWindowFactory {
    @Override public void createToolWindowContent(Project project, ToolWindow window) {
        var view = new View(project);
        var content = ContentFactory.getInstance().createContent(view, "Procedures", false);
        content.setDisposer(view); window.getContentManager().addContent(content);
    }
    private static final DateTimeFormatter DATE = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss z").withZone(ZoneId.systemDefault());
    private static String time(String value) {
        try { if (value.matches("\\d{14,}")) return DATE.format(Instant.ofEpochMilli(Long.parseLong(value) / 1000)); }
        catch (RuntimeException ignored) { }
        return value;
    }
    private static final class View extends JPanel implements Disposable {
        private final Project project;
        private final SpellWorkspace workspace;
        private final JLabel title = new JBLabel("Procedure workspace"), status = new JBLabel("Ready"), subtitle = new JBLabel();
        private final HistoryModel historyModel = new HistoryModel();
        private final CodeModel codeModel = new CodeModel();
        private final JBTable history = new JBTable(historyModel), code = new JBTable(codeModel);
        private final JTextArea output = new JTextArea();
        private final JComboBox<String> sources = new JComboBox<>();
        private final JCheckBox follow = new JCheckBox("Follow current line", true);
        private final JPanel procedureTabs = new JPanel(new FlowLayout(FlowLayout.LEFT, 5, 0));
        private final JLabel role = new JBLabel("CTRL");
        private final JButton claim = new JButton("Take control"), release = new JButton("Release control"), browser = new JButton("Web workspace");
        private final JPanel promptPanel = new JPanel(new BorderLayout(8, 8)), promptBody = new JPanel(new BorderLayout(8, 8));
        private final JLabel promptMessage = new JBLabel();
        private final JButton commit = new JButton("Commit"), reset = new JButton("Reset"), abort = new JButton("Abort procedure");
        private JTextField answerField;
        private ButtonGroup options;
        private String selectedAnswer, renderedPrompt = "";
        private SpellWorkspace.Session renderedSession;
        private boolean refreshing;
        View(Project project) {
            super(new BorderLayout(0, 12)); this.project = project; workspace = SpellWorkspace.get(project);
            setBorder(JBUI.Borders.empty(12));
            JPanel heading = new JPanel(new BorderLayout(12, 8));
            title.setFont(title.getFont().deriveFont(Font.BOLD, title.getFont().getSize2D() + 3));
            status.setBorder(JBUI.Borders.empty(4, 10));
            heading.add(title, BorderLayout.WEST); heading.add(status, BorderLayout.EAST);
            JPanel navigation = new JPanel(new BorderLayout(8, 4));
            navigation.add(new JBScrollPane(procedureTabs, JScrollPane.VERTICAL_SCROLLBAR_NEVER, JScrollPane.HORIZONTAL_SCROLLBAR_AS_NEEDED), BorderLayout.CENTER);
            JButton editor = new JButton("Return to editor"); editor.addActionListener(event -> workspace.restoreLayout()); navigation.add(editor, BorderLayout.EAST);
            heading.add(navigation, BorderLayout.NORTH);
            JPanel north = new JPanel(new BorderLayout(0, 8)); north.add(heading, BorderLayout.NORTH);
            JPanel controls = new JPanel(new BorderLayout(0, 6));
            subtitle.setForeground(JBColor.GRAY); controls.add(subtitle, BorderLayout.NORTH);
            DefaultActionGroup group = new DefaultActionGroup();
            for (String id : new String[]{"OpenBEXI.Spell.Run", "OpenBEXI.Spell.Debug", "OpenBEXI.Spell.Pause", "OpenBEXI.Spell.Continue", "OpenBEXI.Spell.Step", "OpenBEXI.Spell.Stop"})
                group.add(ActionManager.getInstance().getAction(id));
            var toolbar = ActionManager.getInstance().createActionToolbar("OpenBEXI.Spell.ToolWindow", group, true);
            toolbar.setTargetComponent(this); controls.add(toolbar.getComponent(), BorderLayout.CENTER);
            JPanel ownership = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 0));
            JCheckBox showHistory = new JCheckBox("Procedure list", false);
            ownership.add(role); ownership.add(claim); ownership.add(release); ownership.add(browser); ownership.add(showHistory); controls.add(ownership, BorderLayout.SOUTH);
            claim.addActionListener(event -> workspace.control("openbexi/claim")); release.addActionListener(event -> workspace.control("openbexi/release"));
            browser.addActionListener(event -> {
                var current = workspace.selected(); if (current == null || current.endpoint.isBlank()) return;
                try {
                    var config = com.google.gson.JsonParser.parseString(java.nio.file.Files.readString(java.nio.file.Path.of(current.endpoint))).getAsJsonObject();
                    com.intellij.ide.BrowserUtil.browse(config.get("url").getAsString() + "/#key=" + config.get("operator").getAsString());
                } catch (Exception error) { promptMessage.setText(error.getMessage()); }
            });
            north.add(controls, BorderLayout.CENTER); add(north, BorderLayout.NORTH);
            history.setSelectionMode(ListSelectionModel.SINGLE_SELECTION); history.setRowHeight(JBUI.scale(30));
            history.setShowGrid(false); history.setIntercellSpacing(new Dimension(0, 0));
            history.getEmptyText().setText("Your procedure runs will appear here");
            history.getColumnModel().getColumn(0).setPreferredWidth(220);
            history.getColumnModel().getColumn(1).setPreferredWidth(210);
            history.getSelectionModel().addListSelectionListener(event -> {
                if (!refreshing && !event.getValueIsAdjusting() && history.getSelectedRow() >= 0)
                    workspace.select(workspace.sessions().get(history.getSelectedRow()));
            });
            code.setSelectionMode(ListSelectionModel.SINGLE_SELECTION); code.setRowHeight(JBUI.scale(27));
            code.setAutoResizeMode(JTable.AUTO_RESIZE_OFF); code.setShowGrid(false);
            code.getEmptyText().setText("Run a procedure to inspect its code and native results");
            int[] widths = {48, 430, 155, 140, 140, 140};
            for (int index = 0; index < widths.length; index++) code.getColumnModel().getColumn(index).setPreferredWidth(JBUI.scale(widths[index]));
            // Keep labeled columns visible even before the tool window receives its first showing event.
            for (JBTable table : new JBTable[]{history, code}) {
                table.setTableHeader(new JTableHeader(table.getColumnModel()));
                table.getTableHeader().setPreferredSize(new Dimension(table.getPreferredSize().width, JBUI.scale(30)));
                table.getTableHeader().setReorderingAllowed(false);
            }
            code.setDefaultRenderer(Object.class, new DefaultTableCellRenderer() {
                @Override public Component getTableCellRendererComponent(JTable table, Object value, boolean selected, boolean focus, int row, int column) {
                    super.getTableCellRendererComponent(table, value, selected, focus, row, column);
                    setBackground(table.getBackground()); setForeground(Color.BLACK);
                    setBorder(JBUI.Borders.empty(0, 8));
                    setFont(column == 1 ? new Font(Font.MONOSPACED, Font.PLAIN, table.getFont().getSize()) : table.getFont());
                    var session = workspace.selected(); setToolTipText(column == 1 ? String.valueOf(value) : null);
                    if (session != null) {
                        setBackground(SpellPalette.procedure(session.status));
                        var result = session.shownResults().get(row + 1);
                        if (result != null && column > 1) setToolTipText(result.fields.toString());
                        if (session.currentSource.equals(session.selectedSource) && session.currentLine == row + 1 && session.active()) {
                            setBackground(SpellPalette.CURRENT); setForeground(Color.WHITE);
                        }
                        if (column == 5 && result != null && SpellPalette.result(result.result) != null) {
                            setBackground(SpellPalette.result(result.result)); setForeground(Color.BLACK);
                        }
                    }
                    return this;
                }
            });
            code.addMouseListener(new MouseAdapter() {
                @Override public void mouseClicked(MouseEvent event) {
                    if (event.getClickCount() == 2 && code.getSelectedRow() >= 0 && workspace.selected() != null)
                        showInformation(workspace.selected(), code.getSelectedRow() + 1);
                }
            });
            output.setEditable(false); output.setFont(new Font(Font.MONOSPACED, Font.PLAIN, output.getFont().getSize()));
            output.setBorder(JBUI.Borders.empty(8)); var tabs = new JBTabbedPane();
            JPanel codePage = new JPanel(new BorderLayout(0, 5));
            JPanel sourceRow = new JPanel(new BorderLayout(8, 0)); sourceRow.add(sources, BorderLayout.CENTER); sourceRow.add(follow, BorderLayout.EAST); codePage.add(sourceRow, BorderLayout.NORTH);
            sources.addActionListener(event -> {
                if (!refreshing && workspace.selected() != null && sources.getSelectedItem() != null) {
                    workspace.selected().selectedSource = sources.getSelectedItem().toString(); follow.setSelected(false); refresh();
                }
            });
            var codeScroll = new JScrollPane(code); codeScroll.setColumnHeaderView(code.getTableHeader()); codePage.add(codeScroll, BorderLayout.CENTER);
            var note = new JBLabel("Native results and timestamps. Blank cells have no reported result.");
            note.setForeground(JBColor.GRAY); note.setBorder(JBUI.Borders.emptyTop(4)); codePage.add(note, BorderLayout.SOUTH);
            tabs.addTab("Code & results", codePage); tabs.addTab("Output", new JBScrollPane(output));
            var historyScroll = new JScrollPane(history); historyScroll.setColumnHeaderView(history.getTableHeader());
            JSplitPane split = new JSplitPane(JSplitPane.VERTICAL_SPLIT, historyScroll, tabs);
            split.setBorder(JBUI.Borders.empty()); split.setResizeWeight(.25);
            int dividerSize = split.getDividerSize();
            historyScroll.setVisible(false); split.setDividerSize(0); split.setDividerLocation(0);
            showHistory.addActionListener(event -> {
                historyScroll.setVisible(showHistory.isSelected());
                split.setDividerSize(showHistory.isSelected() ? dividerSize : 0);
                split.setDividerLocation(showHistory.isSelected() ? JBUI.scale(140) : 0);
                split.revalidate();
            });
            add(split, BorderLayout.CENTER);
            promptPanel.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createLineBorder(JBColor.border()), JBUI.Borders.empty(12)));
            JPanel footer = new JPanel(new BorderLayout(8, 8)), buttons = new JPanel(new FlowLayout(FlowLayout.LEFT, 8, 0));
            buttons.add(commit); buttons.add(reset); buttons.add(abort); footer.add(buttons, BorderLayout.NORTH); footer.add(promptMessage, BorderLayout.SOUTH);
            promptPanel.add(promptBody, BorderLayout.CENTER); promptPanel.add(footer, BorderLayout.SOUTH);
            promptPanel.setVisible(false); add(promptPanel, BorderLayout.SOUTH);
            commit.addActionListener(event -> submit());
            reset.addActionListener(event -> {
                if (options != null) options.clearSelection(); selectedAnswer = null;
                if (answerField != null) { answerField.setText(""); answerField.requestFocusInWindow(); }
                promptMessage.setText(" ");
            });
            abort.addActionListener(event -> workspace.stop(workspace.selected()));
            workspace.listen(this::refresh, this); refresh();
        }
        private void submit() {
            var session = workspace.selected(); if (session == null || session.prompt == null) return;
            String answer = options == null ? answerField.getText() : selectedAnswer;
            if (answer == null) { promptMessage.setText("Select an answer first."); return; }
            int type = 0; try { type = Integer.parseInt(SpellWorkspace.string(session.prompt, "DataType")); } catch (NumberFormatException ignored) { }
            if (options == null && (type & 16) != 0 && !answer.matches("[+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[eE][+-]?\\d+)?")) {
                promptMessage.setText("Enter a valid number before committing."); return;
            }
            if (answer.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 65536) {
                promptMessage.setText("The answer must be smaller than 64 KiB."); return;
            }
            workspace.answer(session, SpellWorkspace.string(session.prompt, "promptId"), answer);
        }
        private void refresh() {
            refreshing = true;
            try {
                var session = workspace.selected(); historyModel.fireTableDataChanged();
                procedureTabs.removeAll();
                for (var entry : workspace.sessions()) {
                    var button = new JToggleButton(entry.file.getName() + " · " + (entry.serviceId.isBlank() ? entry.started.toString() : entry.serviceId.substring(0, 6)) + " · " + entry.status, entry == session);
                    button.addActionListener(event -> workspace.select(entry)); procedureTabs.add(button);
                }
                procedureTabs.revalidate(); procedureTabs.repaint();
                if (session != null) { int index = workspace.sessions().indexOf(session); if (index >= 0) history.setRowSelectionInterval(index, index); }
                title.setText(session == null ? "Procedure workspace" : session.file.getName()); status.setText(session == null ? "Ready" : session.status);
                boolean controlling = session != null && session.active() && session.controlling && session.connection.equals("Connected");
                role.setText(session != null && !session.active() ? "Record" : controlling ? "CTRL" : "MON"); role.setForeground(controlling ? new Color(0x008000) : Color.BLUE);
                claim.setEnabled(session != null && session.active() && session.controller.isBlank() && session.connection.equals("Connected"));
                release.setEnabled(controlling && java.util.Set.of("PAUSED", "INTERRUPTED", "PROMPT").contains(session.status.toUpperCase(java.util.Locale.ROOT)));
                browser.setEnabled(session != null && !session.endpoint.isBlank());
                status.setOpaque(true); status.setForeground(Color.BLACK); status.setBackground(SpellPalette.procedure(session == null ? "UNKNOWN" : session.status));
                sources.removeAllItems();
                if (session != null) {
                    if (session.active() && follow.isSelected()) session.selectedSource = session.currentSource;
                    for (String path : session.sources.keySet()) sources.addItem(path);
                    sources.setSelectedItem(session.selectedSource);
                }
                subtitle.setText(session == null ? "Open a Python procedure, then choose Run or Debug." : session.connection + " · " + session.file.getPresentableUrl());
                subtitle.setToolTipText(subtitle.getText()); codeModel.fireTableDataChanged();
                if (session != null && session.active() && follow.isSelected() && session.currentLine > 0 && session.currentLine <= code.getRowCount())
                    code.scrollRectToVisible(code.getCellRect(session.currentLine - 1, 0, true));
                String text = session == null ? "" : session.output.toString();
                if (!output.getText().equals(text)) {
                    boolean follow = output.getCaretPosition() == output.getDocument().getLength();
                    output.setText(text); if (follow) output.setCaretPosition(output.getDocument().getLength());
                }
                renderPrompt(session);
            } finally { refreshing = false; }
        }
        private void renderPrompt(SpellWorkspace.Session session) {
            JsonObject prompt = session == null ? null : session.prompt; promptPanel.setVisible(prompt != null);
            if (prompt == null) { renderedPrompt = ""; renderedSession = null; return; }
            String identifier = SpellWorkspace.string(prompt, "promptId");
            if (session != renderedSession || !identifier.equals(renderedPrompt)) {
                renderedSession = session; renderedPrompt = identifier; selectedAnswer = null;
                promptBody.removeAll(); answerField = null; options = null;
                JTextArea question = new JTextArea(SpellWorkspace.string(prompt, "Text"));
                question.setEditable(false); question.setOpaque(false); question.setLineWrap(true); question.setWrapStyleWord(true);
                question.setFont(getFont().deriveFont(Font.BOLD)); question.setRows(Math.min(4, Math.max(2, question.getLineCount())));
                promptBody.add(question, BorderLayout.NORTH);
                String labelsText = SpellWorkspace.string(prompt, "OptionValues"), values = SpellWorkspace.string(prompt, "ExpectedValues");
                int type = 0; try { type = Integer.parseInt(SpellWorkspace.string(prompt, "DataType")); } catch (NumberFormatException ignored) { }
                if (!labelsText.isEmpty() || !values.isEmpty() || (type & 64) != 0) {
                    String[] labels = (labelsText.isEmpty() ? values : labelsText).split("\u0004", -1);
                    options = new ButtonGroup(); JPanel choices = new JPanel(); choices.setLayout(new BoxLayout(choices, BoxLayout.Y_AXIS));
                    for (int index = 0; index < labels.length; index++) {
                        String wire = Integer.toString(index);
                        JRadioButton option = new JRadioButton(labels[index].isEmpty() ? "(empty value)" : labels[index]);
                        option.addActionListener(event -> selectedAnswer = wire); options.add(option); choices.add(option);
                    }
                    var scroll = new JBScrollPane(choices); scroll.setBorder(JBUI.Borders.empty());
                    scroll.setPreferredSize(new Dimension(200, JBUI.scale(Math.min(150, labels.length * 28 + 4)))); promptBody.add(scroll, BorderLayout.CENTER);
                } else {
                    answerField = (type & 4096) != 0 ? new JPasswordField() : new JTextField();
                    answerField.setBackground(Color.YELLOW); answerField.setForeground(Color.BLACK);
                    answerField.setName("SPELL prompt answer"); answerField.getAccessibleContext().setAccessibleName("SPELL prompt answer");
                    answerField.addActionListener(event -> submit());
                    String hint = (type & 16) != 0 ? "Enter a number" : (type & 1024) != 0 ? "Enter a SPELL date, for example 17-Oct-2026 14:30:00" : "Enter your answer";
                    answerField.setToolTipText(hint); promptBody.add(answerField, BorderLayout.CENTER); promptBody.add(new JBLabel(hint), BorderLayout.SOUTH);
                }
                promptBody.revalidate(); promptBody.repaint();
            }
            boolean editable = session.controlling && session.connection.equals("Connected") && !session.answering && session.pending.isBlank();
            commit.setEnabled(editable); reset.setEnabled(editable); abort.setEnabled(session.controlling);
            if (answerField != null) answerField.setEnabled(editable);
            if (options != null) { var buttons = options.getElements(); while (buttons.hasMoreElements()) buttons.nextElement().setEnabled(editable); }
            String message = session.error.isBlank() ? session.answering ? "Submitting answer…" : session.reminded ? "The procedure is waiting for your answer." : " " : session.error;
            if (message.isBlank() && "True".equals(SpellWorkspace.string(prompt, "DefaultProvided")))
                message = "Default answer configured by this procedure: " + SpellWorkspace.string(prompt, "Default");
            promptMessage.setText(message);
            if (!session.controlling) promptMessage.setText("Monitoring: only the controller can answer.");
        }
        @Override public void dispose() { }
        private void showInformation(SpellWorkspace.Session session, int line) {
            if (session.endpoint.isBlank() || session.serviceId.isBlank()) return;
            JComboBox<String> mode = new JComboBox<>(new String[]{"Latest information", "History", "Full"});
            JTextArea details = new JTextArea(20, 100); details.setEditable(false); details.setFont(new Font(Font.MONOSPACED, Font.PLAIN, 13));
            var model = new DefaultTableModel(new String[]{"EX", "Name", "Value", "Status", "Updated", "Stack", "Comments"}, 0) {
                @Override public boolean isCellEditable(int row, int column) { return false; }
            };
            var table = new JBTable(model); var tableScroll = new JBScrollPane(table); var rawScroll = new JBScrollPane(details);
            var pages = new JPanel(new CardLayout()); pages.add(tableScroll, "items"); pages.add(rawScroll, "raw");
            var count = new JBLabel(); var more = new JButton("Load more recorded notifications");
            var entries = new com.google.gson.JsonArray(); final long[] cursor = {0}; final int[] generation = {0};
            final String path = session.selectedSource;
            Runnable render = () -> {
                boolean full = mode.getSelectedIndex() == 2; ((CardLayout)pages.getLayout()).show(pages, full ? "raw" : "items");
                details.setText(full ? new com.google.gson.GsonBuilder().setPrettyPrinting().create().toJson(entries) : "");
                details.setCaretPosition(0);
                var merged = new java.util.LinkedHashMap<String, Object[]>();
                for (var entry : entries) {
                    var record = entry.getAsJsonObject(); var event = record.getAsJsonObject("event");
                    String item = SpellWorkspace.string(event, "item"), value = SpellWorkspace.string(event, "value"), state = SpellWorkspace.string(event, "status");
                    if (item.isBlank() && value.isBlank() && state.isBlank()) continue;
                    var fields = event.has("details") && event.get("details").isJsonObject() ? event.getAsJsonObject("details") : new JsonObject();
                    String[] names = item.split("\u0004", -1), values = value.split("\u0004", -1), states = state.split("\u0004", -1);
                    for (int n = 0; n < names.length; n++) {
                        String iteration = record.get("iteration").getAsString();
                        String key = iteration + "\u0000" + SpellWorkspace.string(event, "procedureId") + "\u0000" + names[n] + "\u0000" + SpellWorkspace.string(fields, "ItemType");
                        merged.put(key, new Object[]{iteration, names[n], n < values.length ? values[n] : "", n < states.length ? states[n] : states.length == 1 ? states[0] : "",
                            SpellWorkspace.string(event, "timestamp"), SpellWorkspace.string(fields, "Csp"), SpellWorkspace.string(fields, "ItemReason")});
                    }
                }
                model.setRowCount(0); merged.values().forEach(model::addRow); count.setText(entries.size() + " recorded notifications loaded");
            };
            Runnable load = () -> {
                int requestGeneration = generation[0]; long after = cursor[0]; boolean latest = mode.getSelectedIndex() == 0; more.setEnabled(false);
                Thread.ofVirtual().start(() -> {
                    try {
                        var page = new SpellRecords(session.endpoint).read(session.serviceId, path, line, after, latest);
                        SwingUtilities.invokeLater(() -> {
                            if (requestGeneration != generation[0]) return;
                            entries.addAll(page); if (!page.isEmpty()) cursor[0] = page.get(page.size() - 1).getAsJsonObject().get("sequence").getAsLong();
                            more.setEnabled(page.size() == 500); render.run();
                        });
                    } catch (Exception error) { SwingUtilities.invokeLater(() -> count.setText(error.getMessage())); }
                });
            };
            mode.addActionListener(event -> { generation[0]++; entries.asList().clear(); cursor[0] = 0; load.run(); });
            more.addActionListener(event -> load.run()); load.run(); JPanel panel = new JPanel(new BorderLayout(8, 8));
            panel.setPreferredSize(new Dimension(1050, 450)); panel.add(mode, BorderLayout.NORTH); panel.add(pages, BorderLayout.CENTER);
            JPanel footer = new JPanel(new BorderLayout()); footer.add(count, BorderLayout.CENTER); footer.add(more, BorderLayout.EAST); panel.add(footer, BorderLayout.SOUTH);
            JOptionPane.showMessageDialog(this, panel, "Item information · line " + line, JOptionPane.PLAIN_MESSAGE);
        }
        private final class HistoryModel extends AbstractTableModel {
            private final String[] columns = {"Procedure", "Started (local)", "Result", "Mode"};
            @Override public int getRowCount() { return workspace == null ? 0 : workspace.sessions().size(); }
            @Override public int getColumnCount() { return columns.length; }
            @Override public String getColumnName(int column) { return columns[column]; }
            @Override public Object getValueAt(int row, int column) {
                var session = workspace.sessions().get(row);
                return switch (column) { case 0 -> session.file.getName(); case 1 -> DATE.format(session.started);
                    case 2 -> session.status + (session.exitCode == null ? "" : " (" + session.exitCode + ")"); default -> session.mode; };
            }
        }
        private final class CodeModel extends AbstractTableModel {
            private final String[] columns = {"Line", "Procedure code", "Native date & time", "Item", "Value", "Result"};
            @Override public int getRowCount() { return workspace == null || workspace.selected() == null ? 0 : workspace.selected().shownSource().length; }
            @Override public int getColumnCount() { return columns.length; }
            @Override public String getColumnName(int column) { return columns[column]; }
            @Override public Object getValueAt(int row, int column) {
                var session = workspace.selected(); var result = session.shownResults().get(row + 1);
                if (column == 0) return row + 1; if (column == 1) return session.shownSource()[row]; if (result == null) return "";
                return switch (column) { case 2 -> time(result.time); case 3 -> result.item; case 4 -> result.value; default -> result.result; };
            }
        }
    }
}
