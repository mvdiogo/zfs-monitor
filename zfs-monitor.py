#!/usr/bin/env python3.11
import os
import subprocess
import re
import gi
import threading
import json
import time
from datetime import datetime
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('AyatanaAppIndicator3', '0.1')
from gi.repository import Gtk, Gdk, GLib, AyatanaAppIndicator3 as AppIndicator3, Pango

POOL_NAME = "zhome"
REFRESH_INTERVAL = 5  # seconds for performance updates
STATUS_REFRESH = 30   # seconds for full status updates
ALERT_REFRESH = 60    # seconds for alert checks

# Check if monitoring is enabled
if os.environ.get("ZPOOL_MONITOR_ENABLE", "0") != "1":
    print("ZPOOL_MONITOR_ENABLE variable not set. Exiting.")
    exit(0)

# Function to run system commands with robust error handling
def run_command(cmd, timeout=10):
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return f"Error {result.returncode}: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "Timeout: Command took too long to execute"
    except Exception as e:
        return f"Unexpected error: {str(e)}"

# Function to create formatted labels
def create_formatted_label(text, color=None, bold=False, size=None, monospace=False, halign=Gtk.Align.START):
    label = Gtk.Label()
    label.set_markup(text)
    label.set_line_wrap(True)
    label.set_selectable(True)
    label.set_halign(halign)
    
    attrs = Pango.AttrList()
    if color:
        r, g, b = [int(c * 65535) for c in color]
        color_attr = Pango.attr_foreground_new(r, g, b)
        attrs.insert(color_attr)
    if bold:
        bold_attr = Pango.attr_weight_new(Pango.Weight.BOLD)
        attrs.insert(bold_attr)
    if size:
        size_attr = Pango.attr_scale_new(size)
        attrs.insert(size_attr)
    if monospace:
        font_attr = Pango.attr_family_new("Monospace")
        attrs.insert(font_attr)
    
    label.set_attributes(attrs)
    return label

# Loading spinner widget
class LoadingSpinner(Gtk.Spinner):
    def __init__(self):
        super().__init__()
        self.set_size_request(24, 24)
    
    def start(self):
        self.show()
        super().start()
    
    def stop(self):
        super().stop()
        self.hide()

# Status Tab
class StatusTab(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.main_box.set_margin_start(20)
        self.main_box.set_margin_end(20)
        self.main_box.set_margin_top(20)
        self.main_box.set_margin_bottom(20)
        
        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = create_formatted_label(f"<big><b>Status do Pool ZFS: {POOL_NAME}</b></big>")
        header.pack_start(title, False, False, 0)
        
        self.spinner = LoadingSpinner()
        header.pack_end(self.spinner, False, False, 0)
        self.main_box.pack_start(header, False, False, 0)
        
        # Info container
        self.info_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.pack_start(self.info_container, True, True, 0)
        
        # Action buttons
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        refresh_btn = Gtk.Button.new_with_label("↻ Atualizar")
        refresh_btn.connect("clicked", self.refresh)
        action_box.pack_start(refresh_btn, False, False, 0)
        
        scrub_btn = Gtk.Button.new_with_label("⏱ Iniciar Scrub")
        scrub_btn.connect("clicked", self.start_scrub)
        action_box.pack_start(scrub_btn, False, False, 0)
        
        export_btn = Gtk.Button.new_with_label("💾 Exportar Status")
        export_btn.connect("clicked", self.export_status)
        action_box.pack_start(export_btn, False, False, 0)
        
        self.main_box.pack_end(action_box, False, False, 0)
        
        self.add(self.main_box)
        self.refresh()
    
    def start_scrub(self, widget):
        widget.set_sensitive(False)
        widget.set_label("⏳ Executando...")
        
        def do_scrub():
            result = run_command(f"zpool scrub {POOL_NAME}", timeout=300)
            GLib.idle_add(lambda: widget.set_sensitive(True))
            GLib.idle_add(lambda: widget.set_label("⏱ Iniciar Scrub"))
            GLib.idle_add(self.refresh)
            if "Erro" not in result:
                GLib.idle_add(self.show_notification, "Scrub iniciado", "A operação de scrub foi iniciada com sucesso")
            else:
                GLib.idle_add(self.show_notification, "Erro no scrub", result)
        
        threading.Thread(target=do_scrub, daemon=True).start()
    
    def export_status(self, widget):
        dialog = Gtk.FileChooserDialog(
            title="Exportar Status",
            parent=None,
            action=Gtk.FileChooserAction.SAVE,
            buttons=("_Cancelar", Gtk.ResponseType.CANCEL, "_Salvar", Gtk.ResponseType.OK)
        )
        dialog.set_current_name(f"zfs_status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
            try:
                output = run_command(f"zpool status -v {POOL_NAME}")
                with open(filename, 'w') as f:
                    f.write(output)
                self.show_notification("Exportação concluída", f"Status salvo em {filename}")
            except Exception as e:
                self.show_notification("Erro na exportação", str(e))
        
        dialog.destroy()
    
    def show_notification(self, title, message):
        dialog = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
    
    def refresh(self, widget=None):
        self.spinner.start()
        # Clear container
        for child in self.info_container.get_children():
            self.info_container.remove(child)
        
        # Add placeholder
        placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        placeholder.set_valign(Gtk.Align.CENTER)
        placeholder.pack_start(create_formatted_label("Coletando dados...", halign=Gtk.Align.CENTER), True, True, 0)
        self.info_container.pack_start(placeholder, True, True, 0)
        self.show_all()
        
        # Run in thread
        def fetch_data():
            output = run_command(f"zpool status {POOL_NAME}", timeout=15)
            info = self.parse_zpool_status(output)
            GLib.idle_add(self.update_ui, info)
        
        threading.Thread(target=fetch_data, daemon=True).start()
    
    def parse_zpool_status(self, output):
        info = {}
        lines = output.split('\n')
        
        # Basic parsing
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('pool:'):
                info['pool'] = line.split(':', 1)[1].strip()
            elif line.startswith('state:'):
                info['state'] = line.split(':', 1)[1].strip()
            elif line.startswith('status:'):
                info['status'] = line.split(':', 1)[1].strip()
                # Capture multi-line
                j = i + 1
                while j < len(lines) and not lines[j].startswith(('action:', 'see:', 'scan:', 'config:')):
                    if lines[j].strip():
                        info['status'] += "\n" + lines[j].strip()
                    j += 1
            elif line.startswith('action:'):
                info['action'] = line.split(':', 1)[1].strip()
            elif line.startswith('scan:'):
                info['scan'] = line.split(':', 1)[1].strip()
            elif line.startswith('errors:'):
                info['errors'] = line.split(':', 1)[1].strip()
            elif line.startswith('config:'):
                # Capture entire config section
                config_lines = []
                j = i + 1
                while j < len(lines) and not lines[j].startswith('errors:'):
                    config_lines.append(lines[j])
                    j += 1
                info['config'] = "\n".join(config_lines)
        
        return info
    
    def update_ui(self, info):
        self.spinner.stop()
        # Clear container
        for child in self.info_container.get_children():
            self.info_container.remove(child)
        
        if 'state' not in info:
            self.info_container.pack_start(
                create_formatted_label(f"<b>Erro ao obter status:</b>\n<tt>{info.get('raw', 'Sem dados')}</tt>", color=(1,0,0)),
                True, True, 0
            )
            return
        
        # Pool State
        state = info['state']
        if state == 'ONLINE':
            state_label = create_formatted_label(f"<b>Estado:</b> <span color='#2ecc71'>[OK] {state}</span>")
        elif state in ['DEGRADED', 'FAULTED']:
            state_label = create_formatted_label(f"<b>Estado:</b> <span color='#e74c3c'>[ERRO] {state}</span>")
        else:
            state_label = create_formatted_label(f"<b>Estado:</b> <span color='#f1c40f'>[ATENÇÃO] {state}</span>")
        
        self.info_container.pack_start(state_label, False, False, 0)
        
        # Status/Issues
        if 'status' in info:
            status_text = info['status']
            if any(word in status_text.upper() for word in ['MISSING', 'INVALID', 'DEGRADED', 'FAULTED']):
                status_label = create_formatted_label(f"<b>⚠ ATENÇÃO - Problema Detectado:</b>\n<span color='#e74c3c'>{status_text}</span>")
            else:
                status_label = create_formatted_label(f"<b>Status:</b>\n{status_text}")
            self.info_container.pack_start(status_label, False, False, 0)
        
        # Recommended Action
        if 'action' in info:
            action_label = create_formatted_label(f"<b>⚙ Ação Recomendada:</b>\n<span color='#3498db'>{info['action']}</span>")
            self.info_container.pack_start(action_label, False, False, 0)
        
        # Last Scan
        if 'scan' in info:
            scan_label = create_formatted_label(f"<b>≡ Último Scan:</b> {info['scan']}")
            self.info_container.pack_start(scan_label, False, False, 0)
        
        # Errors
        if 'errors' in info:
            errors = info['errors']
            if errors.lower() != 'no known data errors':
                error_label = create_formatted_label(f"<b>⚠ Erros:</b> <span color='#e74c3c'>{errors}</span>")
            else:
                error_label = create_formatted_label(f"<b>✓ Erros:</b> <span color='#2ecc71'>{errors}</span>")
            self.info_container.pack_start(error_label, False, False, 0)
        
        # Device Configuration
        if 'config' in info:
            separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            self.info_container.pack_start(separator, False, False, 10)
            
            config_title = create_formatted_label("<b>▣ Configuração dos Dispositivos:</b>")
            self.info_container.pack_start(config_title, False, False, 0)
            
            config_frame = Gtk.Frame()
            config_frame.set_shadow_type(Gtk.ShadowType.IN)
            
            config_view = Gtk.TextView()
            config_view.set_editable(False)
            config_view.set_cursor_visible(False)
            config_view.set_monospace(True)
            config_view.get_buffer().set_text(info['config'])
            
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_min_content_height(200)
            scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scrolled.add(config_view)
            
            config_frame.add(scrolled)
            self.info_container.pack_start(config_frame, True, True, 0)
        
        self.show_all()

# Performance Tab
class PerformanceTab(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.main_box.set_margin_start(20)
        self.main_box.set_margin_end(20)
        self.main_box.set_margin_top(20)
        self.main_box.set_margin_bottom(20)
        
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = create_formatted_label(f"<big><b>Desempenho em Tempo Real - {POOL_NAME}</b></big>")
        header.pack_start(title, False, False, 0)
        
        self.spinner = LoadingSpinner()
        header.pack_end(self.spinner, False, False, 0)
        self.main_box.pack_start(header, False, False, 0)
        
        self.stats_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.pack_start(self.stats_container, True, True, 0)
        
        # Controls
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        self.interval_combo = Gtk.ComboBoxText()
        self.interval_combo.append_text("Atualização rápida (2s)")
        self.interval_combo.append_text("Atualização normal (5s)")
        self.interval_combo.append_text("Atualização lenta (10s)")
        self.interval_combo.set_active(1)
        self.interval_combo.connect("changed", self.change_interval)
        controls_box.pack_start(self.interval_combo, False, False, 0)
        
        history_btn = Gtk.Button.new_with_label("📈 Histórico (Última hora)")
        history_btn.connect("clicked", self.show_history)
        controls_box.pack_end(history_btn, False, False, 0)
        
        self.main_box.pack_end(controls_box, False, False, 0)
        
        self.add(self.main_box)
        self.timeout_id = None
        self.change_interval()
    
    def change_interval(self, widget=None):
        if self.timeout_id:
            GLib.source_remove(self.timeout_id)
        
        index = self.interval_combo.get_active()
        intervals = [2, 5, 10]
        interval = intervals[index]
        
        self.timeout_id = GLib.timeout_add_seconds(interval, self.refresh)
        self.refresh()
    
    def show_history(self, widget):
        dialog = Gtk.Dialog(
            title=f"Histórico de Desempenho - {POOL_NAME}",
            parent=None,
            flags=0
        )
        dialog.set_default_size(600, 400)
        
        content = dialog.get_content_area()
        content.pack_start(create_formatted_label("Histórico de desempenho (em desenvolvimento)"), True, True, 0)
        
        dialog.add_button("_Fechar", Gtk.ResponseType.CLOSE)
        dialog.show_all()
        dialog.run()
        dialog.destroy()
    
    def refresh(self):
        self.spinner.start()
        # Clear container
        for child in self.stats_container.get_children():
            self.stats_container.remove(child)
        
        # Run in thread
        def fetch_data():
            output = run_command(f"zpool iostat -v {POOL_NAME} 1 1", timeout=8)
            stats = self.parse_iostat(output)
            GLib.idle_add(self.update_ui, stats)
        
        threading.Thread(target=fetch_data, daemon=True).start()
        return True
    
    def parse_iostat(self, output):
        lines = output.split('\n')
        data = {}
        current_section = None
        
        for line in lines:
            # Skip headers
            if 'capacity' in line and 'operations' in line and 'bandwidth' in line:
                continue
            if line.startswith('pool'):
                continue
            if not line.strip() or line.startswith('-'):
                continue
            
            # Main device
            if not line.startswith(' '):
                parts = line.split()
                if len(parts) >= 7:
                    name = parts[0]
                    data[name] = {
                        'alloc': parts[1],
                        'free': parts[2],
                        'read_ops': parts[3],
                        'write_ops': parts[4],
                        'read_bw': parts[5],
                        'write_bw': parts[6]
                    }
                    current_section = name
            # Sub-devices
            elif current_section:
                parts = line.strip().split()
                if len(parts) >= 7:
                    name = parts[0]
                    data[name] = {
                        'alloc': parts[1],
                        'free': parts[2],
                        'read_ops': parts[3],
                        'write_ops': parts[4],
                        'read_bw': parts[5],
                        'write_bw': parts[6]
                    }
        
        return data
    
    def update_ui(self, stats):
        self.spinner.stop()
        if POOL_NAME not in stats:
            self.stats_container.pack_start(
                create_formatted_label(f"<b>Erro ao obter estatísticas:</b>\n{stats}", color=(1,0,0)),
                True, True, 0
            )
            return
        
        pool_stats = stats[POOL_NAME]
        
        # Stats grid
        grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        grid.set_margin_top(10)
        
        # Headers
        grid.attach(create_formatted_label("<b>Métrica</b>", bold=True), 0, 0, 1, 1)
        grid.attach(create_formatted_label("<b>Valor</b>", bold=True, halign=Gtk.Align.END), 1, 0, 1, 1)
        
        # Data
        metrics = [
            ("Capacidade Alocada", pool_stats['alloc']),
            ("Espaço Livre", pool_stats['free']),
            ("Operações Leitura/s", pool_stats['read_ops']),
            ("Operações Escrita/s", pool_stats['write_ops']),
            ("Largura Banda Leitura", pool_stats['read_bw']),
            ("Largura Banda Escrita", pool_stats['write_bw'])
        ]
        
        for i, (label, value) in enumerate(metrics, start=1):
            grid.attach(create_formatted_label(label), 0, i, 1, 1)
            grid.attach(create_formatted_label(value, halign=Gtk.Align.END), 1, i, 1, 1)
        
        self.stats_container.pack_start(grid, False, False, 20)
        
        # Devices
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.stats_container.pack_start(separator, False, False, 10)
        
        devices_title = create_formatted_label("<b>▣ Desempenho por Dispositivo</b>")
        self.stats_container.pack_start(devices_title, False, False, 0)
        
        # Devices table
        devices_grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        devices_grid.set_margin_top(10)
        
        headers = ["Dispositivo", "Alocado", "Livre", "Ops R", "Ops W", "BW R", "BW W"]
        for col, header in enumerate(headers):
            devices_grid.attach(create_formatted_label(f"<b>{header}</b>", bold=True), col, 0, 1, 1)
        
        row = 1
        for device, device_stats in stats.items():
            if device == POOL_NAME:
                continue
            devices_grid.attach(create_formatted_label(device), 0, row, 1, 1)
            devices_grid.attach(create_formatted_label(device_stats['alloc'], halign=Gtk.Align.END), 1, row, 1, 1)
            devices_grid.attach(create_formatted_label(device_stats['free'], halign=Gtk.Align.END), 2, row, 1, 1)
            devices_grid.attach(create_formatted_label(device_stats['read_ops'], halign=Gtk.Align.END), 3, row, 1, 1)
            devices_grid.attach(create_formatted_label(device_stats['write_ops'], halign=Gtk.Align.END), 4, row, 1, 1)
            devices_grid.attach(create_formatted_label(device_stats['read_bw'], halign=Gtk.Align.END), 5, row, 1, 1)
            devices_grid.attach(create_formatted_label(device_stats['write_bw'], halign=Gtk.Align.END), 6, row, 1, 1)
            row += 1
        
        self.stats_container.pack_start(devices_grid, False, False, 0)
        self.show_all()

# Alerts Tab
class AlertsTab(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.main_box.set_margin_start(20)
        self.main_box.set_margin_end(20)
        self.main_box.set_margin_top(20)
        self.main_box.set_margin_bottom(20)
        
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = create_formatted_label(f"<big><b>Monitoramento de Alertas - {POOL_NAME}</b></big>")
        header.pack_start(title, False, False, 0)
        
        self.spinner = LoadingSpinner()
        header.pack_end(self.spinner, False, False, 0)
        self.main_box.pack_start(header, False, False, 0)
        
        self.alerts_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.pack_start(self.alerts_container, True, True, 0)
        
        self.add(self.main_box)
        self.timeout_id = GLib.timeout_add_seconds(ALERT_REFRESH, self.check_alerts)
        self.check_alerts()
    
    def check_alerts(self):
        self.spinner.start()
        # Clear container
        for child in self.alerts_container.get_children():
            self.alerts_container.remove(child)
        
        # Run in thread
        def fetch_data():
            output = run_command(f"zpool status {POOL_NAME}", timeout=15)
            problems = self.detect_problems(output)
            GLib.idle_add(self.update_ui, problems)
        
        threading.Thread(target=fetch_data, daemon=True).start()
        return True
    
    def detect_problems(self, output):
        problems = []
        
        # Problem detection
        if "DEGRADED" in output:
            problems.append(("CRÍTICO", "Pool em estado DEGRADED", 
                            "O pool está funcionando com capacidade reduzida. Substitua dispositivos com falha imediatamente."))
        
        if "FAULTED" in output:
            problems.append(("CRÍTICO", "Pool em estado FAULTED", 
                            "O pool tem falhas graves. Dados podem estar em risco. Ação imediata necessária."))
        
        if "UNAVAIL" in output:
            problems.append(("ALERTA", "Dispositivo indisponível", 
                            "Um ou mais dispositivos não estão acessíveis. Verifique conexões e hardware."))
        
        if "missing or invalid" in output.lower():
            problems.append(("ALERTA", "Label ausente ou inválido", 
                            "Dispositivos com labels ausentes ou inválidos detectados. Pode afetar a redundância."))
        
        if re.search(r'errors:\s*[1-9]', output.lower()):
            problems.append(("ALERTA", "Erros de dados detectados", 
                            "Foram encontrados erros de leitura/escrita/checksum. Monitore a situação."))
        
        # Check scrub
        scrub_match = re.search(r'scrub.*?(\d{4}-\d{2}-\d{2})', output)
        if scrub_match:
            last_scrub = scrub_match.group(1)
            try:
                last_date = datetime.strptime(last_scrub, "%Y-%m-%d")
                days_ago = (datetime.now() - last_date).days
                if days_ago > 30:
                    problems.append(("RECOMENDAÇÃO", "Scrub desatualizado", 
                                    f"Último scrub foi há {days_ago} dias. Recomenda-se executar scrub."))
            except ValueError:
                pass
        
        return problems
    
    def update_ui(self, problems):
        self.spinner.stop()
        if not problems:
            # Healthy pool
            success_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            success_box.set_valign(Gtk.Align.CENTER)
            success_box.set_halign(Gtk.Align.CENTER)
            
            icon = Gtk.Image.new_from_icon_name("emblem-default", Gtk.IconSize.DIALOG)
            success_box.pack_start(icon, False, False, 0)
            
            title = create_formatted_label("<big><b>✓ Pool Saudável</b></big>", color=(0.18, 0.80, 0.44))
            success_box.pack_start(title, False, False, 0)
            
            msg = create_formatted_label("Não foram detectados problemas críticos no momento.")
            success_box.pack_start(msg, False, False, 0)
            
            self.alerts_container.pack_start(success_box, True, True, 0)
        else:
            for severity, title, description in problems:
                alert_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
                alert_box.set_margin_top(10)
                alert_box.set_margin_bottom(10)
                
                # Header with icon
                header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                
                if severity == "CRÍTICO":
                    icon_name = "dialog-error"
                    color = (0.91, 0.30, 0.24)
                elif severity == "ALERTA":
                    icon_name = "dialog-warning"
                    color = (0.95, 0.75, 0.06)
                else:
                    icon_name = "dialog-information"
                    color = (0.20, 0.60, 0.86)
                
                icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
                header_box.pack_start(icon, False, False, 0)
                
                title_label = create_formatted_label(f"<b>{severity}: {title}</b>", color=color)
                header_box.pack_start(title_label, False, False, 0)
                
                alert_box.pack_start(header_box, False, False, 0)
                
                # Description
                desc_label = create_formatted_label(description)
                alert_box.pack_start(desc_label, False, False, 0)
                
                self.alerts_container.pack_start(alert_box, False, False, 0)
        
        # Useful commands
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.alerts_container.pack_start(separator, False, False, 10)
        
        commands_title = create_formatted_label("<b>⚙ Comandos Úteis</b>")
        self.alerts_container.pack_start(commands_title, False, False, 0)
        
        commands = [
            "zpool scrub zhome  # Verificar integridade",
            "zpool status -v    # Status detalhado",
            "zpool clear zhome  # Limpar erros",
            "zpool replace zhome dispositivo  # Substituir dispositivo"
        ]
        
        for cmd in commands:
            cmd_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            cmd_box.pack_start(create_formatted_label("• "), False, False, 0)
            cmd_box.pack_start(create_formatted_label(f"<tt>{cmd}</tt>"), False, False, 0)
            self.alerts_container.pack_start(cmd_box, False, False, 0)
        
        self.show_all()

# Main Window with Tabs
class ZpoolMonitorWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title=f"Monitor ZFS - {POOL_NAME}")
        self.set_default_size(800, 600)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("delete-event", self.on_close)
        
        notebook = Gtk.Notebook()
        
        notebook.set_tab_pos(Gtk.PositionType.TOP)
        
        # Tabs with icons
        status_tab = StatusTab()
        status_label = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        status_label.pack_start(Gtk.Image.new_from_icon_name("drive-harddisk", Gtk.IconSize.MENU), False, False, 0)
        status_label.pack_start(Gtk.Label(label="Status"), False, False, 0)
        notebook.append_page(status_tab, status_label)
        
        performance_tab = PerformanceTab()
        performance_label = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        performance_label.pack_start(Gtk.Image.new_from_icon_name("utilities-system-monitor", Gtk.IconSize.MENU), False, False, 0)
        performance_label.pack_start(Gtk.Label(label="Desempenho"), False, False, 0)
        notebook.append_page(performance_tab, performance_label)
        
        alerts_tab = AlertsTab()
        alerts_label = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        alerts_label.pack_start(Gtk.Image.new_from_icon_name("dialog-warning", Gtk.IconSize.MENU), False, False, 0)
        alerts_label.pack_start(Gtk.Label(label="Alertas"), False, False, 0)
        notebook.append_page(alerts_tab, alerts_label)
        
        self.add(notebook)
        
        # Apply CSS
        css_provider = Gtk.CssProvider()
        css = b"""
        window {
            background-color: #f5f6f5;
            font-family: 'Segoe UI', sans-serif;
        }
        box, grid, frame {
            background-color: #ffffff;
            border-radius: 8px;
            padding: 12px;
            margin: 8px;
        }
        button {
            background-color: #3498db;
            color: white;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
            transition: background-color 0.2s;
        }
        button:hover {
            background-color: #2980b9;
        }
        button:active {
            background-color: #2c3e50;
        }
        .alert-box {
            background-color: #fff5f5;
            border: 1px solid #ffcccc;
            border-radius: 8px;
            padding: 12px;
            margin: 8px;
        }
        separator {
            background-color: #e0e0e0;
            margin: 12px 0;
        }
        textview {
            background-color: #f8f9fa;
            font-family: 'Monospace';
            padding: 10px;
            border-radius: 4px;
        }
        notebook tab {
            background-color: #ecf0f1;
            border-radius: 6px 6px 0 0;
            padding: 8px 12px;
            font-weight: 500;
        }
        notebook tab:checked {
            background-color: #ffffff;
            border-bottom: 2px solid #3498db;
        }
        label {
            font-size: 11pt;
            color: #2c3e50;
        }
        """
        css_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    def on_close(self, window, event):
        window.hide()
        return True  # Prevent closing, just hide

# System Tray Icon and Control
class TrayApp:
    def __init__(self):
        self.indicator = AppIndicator3.Indicator.new(
            "zfs-monitor", "drive-harddisk",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title(f"ZFS Monitor - {POOL_NAME}")
        
        self.menu = Gtk.Menu()
        
        # Item: Open Window
        item_open = Gtk.MenuItem(label="Abrir Monitor")
        item_open.connect("activate", self.show_window)
        self.menu.append(item_open)
        
        # Item: Quick Status
        item_status = Gtk.MenuItem(label="Verificar Status")
        item_status.connect("activate", self.quick_status)
        self.menu.append(item_status)
        
        # Separator
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Item: Quit
        item_quit = Gtk.MenuItem(label="Sair")
        item_quit.connect("activate", self.quit)
        self.menu.append(item_quit)
        
        self.menu.show_all()
        self.indicator.set_menu(self.menu)
        
        self.window = ZpoolMonitorWindow()
        
        # Background status monitoring
        self.timeout_id = GLib.timeout_add_seconds(STATUS_REFRESH, self.update_tray_status)
        self.update_tray_status()
    
    def show_window(self, _):
        if not self.window.get_visible():
            self.window.show_all()
        self.window.present()
    
    def quick_status(self, _):
        output = run_command(f"zpool status {POOL_NAME}", timeout=10)
        
        if "DEGRADED" in output or "FAULTED" in output:
            dialog = Gtk.MessageDialog(
                transient_for=None,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Problema Grave Detectado!"
            )
            dialog.format_secondary_text(
                f"O pool {POOL_NAME} está em estado crítico. Abra o monitor para detalhes."
            )
        elif "errors:" in output and "No known data errors" not in output:
            dialog = Gtk.MessageDialog(
                transient_for=None,
                flags=0,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text="Problemas Detectados"
            )
            dialog.format_secondary_text(
                f"Foram encontrados erros no pool {POOL_NAME}. Verifique o monitor."
            )
        else:
            dialog = Gtk.MessageDialog(
                transient_for=None,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Pool Saudável"
            )
            dialog.format_secondary_text(f"O pool {POOL_NAME} está funcionando normalmente.")
        
        dialog.run()
        dialog.destroy()
    
    def update_tray_status(self):
        output = run_command(f"zpool status {POOL_NAME}", timeout=10)
        
        if "DEGRADED" in output or "FAULTED" in output:
            self.indicator.set_icon_full("dialog-error", "Pool ZFS em estado crítico")
            self.indicator.set_title(f"ZFS: {POOL_NAME} [CRÍTICO]")
            self.show_alert_notification("Pool em estado crítico!", "Abra o monitor para detalhes.")
        elif "errors:" in output and "No known data errors" not in output:
            self.indicator.set_icon_full("dialog-warning", "Problemas no pool ZFS")
            self.indicator.set_title(f"ZFS: {POOL_NAME} [ALERTA]")
        else:
            self.indicator.set_icon_full("drive-harddisk", "Pool ZFS saudável")
            self.indicator.set_title(f"ZFS: {POOL_NAME} [OK]")
        
        return True
    
    def show_alert_notification(self, title, message):
        # System notification
        notification = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        notification.format_secondary_text(message)
        notification.run()
        notification.destroy()
    
    def quit(self, _):
        if self.timeout_id:
            GLib.source_remove(self.timeout_id)
        Gtk.main_quit()

# Check if pool exists before starting
def check_pool_exists():
    output = run_command(f"zpool list {POOL_NAME}", timeout=5)
    return POOL_NAME in output

# Initialization
if __name__ == "__main__":
    # Check for graphical environment
    if "DISPLAY" not in os.environ:
        print("Graphical environment not detected. Exiting.")
        exit(1)
    
    # Check if pool exists
    if not check_pool_exists():
        dialog = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Pool ZFS não encontrado"
        )
        dialog.format_secondary_text(
            f"O pool '{POOL_NAME}' não foi encontrado no sistema. "
            "Verifique o nome do pool e tente novamente."
        )
        dialog.run()
        dialog.destroy()
        exit(1)
    
    # Start application
    app = TrayApp()
    Gtk.main()
