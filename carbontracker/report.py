import re
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import io

# Set the style for all plots
sns.set_style("whitegrid")
sns.set_palette("husl")
plt.rcParams.update({
    'figure.dpi': 600,
    'savefig.dpi': 600,
    'font.size': 14,
    'axes.labelsize': 14,
    'axes.titlesize': 14,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.titlesize': 13
})

def format_duration(seconds):
    """Convert seconds to a human-readable duration string."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}min")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)

class LogParser:
    def __init__(self, log_content):
        self.log_content = log_content
        self.epochs = []
        self.carbon_intensity = None
        self.location = None
        self.version = None
        self.pue = None
        self.components = None
        self.start_time = None
        self.end_time = None
        self._parse_log()
    
    def _parse_log(self):
        # Parse version and PUE info
        version_match = re.search(r'carbontracker version ([\d\.]+)', self.log_content)
        if version_match:
            self.version = version_match.group(1)
            
        pue_match = re.search(r'PUE coefficient of ([\d\.]+)', self.log_content)
        if pue_match:
            self.pue = float(pue_match.group(1))
        
        # Parse components
        components_match = re.search(r'The following components were found: (.*)', self.log_content)
        if components_match:
            self.components = components_match.group(1)
        
        # Parse epochs
        epoch_pattern = r'Epoch (\d+):\n.*?Duration: ([\d:\.]+)\n.*?Average power usage \(W\) for gpu: ([\d\.]+)\n.*?Average power usage \(W\) for cpu: ([\d\.]+)'
        epoch_matches = re.finditer(epoch_pattern, self.log_content, re.DOTALL)
        
        for match in epoch_matches:
            epoch_num = int(match.group(1))
            duration = self._parse_duration(match.group(2))
            gpu_power = float(match.group(3))
            cpu_power = float(match.group(4))
            
            self.epochs.append({
                'epoch': epoch_num,
                'duration': duration,
                'gpu_power': gpu_power,
                'cpu_power': cpu_power,
                'total_power': gpu_power + cpu_power
            })
        
        # Parse carbon intensity
        ci_match = re.search(r'Average carbon intensity during training was ([\d\.]+) gCO2/kWh at detected location: (.*)', self.log_content)
        if ci_match:
            self.carbon_intensity = float(ci_match.group(1))
            self.location = ci_match.group(2)
        
        # Parse timestamps
        timestamp_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'
        timestamps = re.findall(timestamp_pattern, self.log_content)
        if timestamps:
            self.start_time = timestamps[0]
            self.end_time = timestamps[-1]

    def _parse_duration(self, duration_str):
        parts = duration_str.split(':')
        if len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + float(parts[1])
        return float(duration_str)

    def calculate_energy_metrics(self):
        total_duration = sum(epoch['duration'] for epoch in self.epochs)
        avg_gpu_power = sum(epoch['gpu_power'] for epoch in self.epochs) / len(self.epochs)
        avg_cpu_power = sum(epoch['cpu_power'] for epoch in self.epochs) / len(self.epochs)
        total_power = avg_gpu_power + avg_cpu_power
        
        # Calculate energy in kWh
        energy_kwh = (total_power * total_duration) / 3600 / 1000
        
        # Calculate CO2 emissions in kg
        co2_kg = (energy_kwh * self.carbon_intensity) / 1000
        
        return {
            'total_duration': total_duration,
            'avg_gpu_power': avg_gpu_power,
            'avg_cpu_power': avg_cpu_power,
            'total_power': total_power,
            'energy_kwh': energy_kwh,
            'co2_kg': co2_kg
        }

    def generate_plots(self):
        # Convert epochs to DataFrame
        df = pd.DataFrame(self.epochs)
        
        # Calculate metrics
        df['cumulative_time'] = df['duration'].cumsum() / 60  # Keep this for x-axis
        df['energy_kwh'] = df['total_power'] * df['duration'] / 3600 / 1000
        df['co2_kg'] = df['energy_kwh'] * self.carbon_intensity / 1000
        
        # Color scheme
        colors = {
            'primary': '#1A237E',
            'accent_blue': '#0072B2',
            'accent_orange': '#E69F00',
            'accent_green': '#009E73',
            'co2': '#D55E00',
            'grid': '#C5CAE9'
        }
        
        # Create figure
        fig = plt.figure(figsize=(10, 6), constrained_layout=True)
        gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1], width_ratios=[1, 1], hspace=0.1, wspace=0.05)
        
        # Power usage plot (top)
        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(df['cumulative_time'], df['gpu_power'], label='GPU', linewidth=3.5, marker='o', markersize=5, color=colors['accent_blue'])
        ax1.plot(df['cumulative_time'], df['cpu_power'], label='CPU', linewidth=3.5, marker='s', markersize=5, color=colors['accent_orange'])
        ax1.plot(df['cumulative_time'], df['total_power'], label='Total', linewidth=3.5, linestyle='--', marker='^', markersize=5, color=colors['accent_green'])
        ax1.set_title('Power Usage Over Time', pad=10, fontsize=12, color=colors['primary'])
        ax1.set_xlabel('Time (minutes)', fontsize=10)
        ax1.set_ylabel('Power (W)', fontsize=10)
        ax1.legend(loc='upper right', frameon=True, fancybox=True, shadow=True, fontsize=9)
        ax1.grid(True, alpha=0.5, color=colors['grid'], linestyle='-', linewidth=0.8)
        
        # Energy per epoch plot (bottom left)
        ax2 = fig.add_subplot(gs[1, 0])
        ax2.bar(df['epoch'], df['energy_kwh'], color=colors['accent_blue'], alpha=0.7)
        ax2.set_title('Energy per Epoch', pad=10, fontsize=12, color=colors['primary'])
        ax2.set_xlabel('Epoch', fontsize=10)
        ax2.set_ylabel('Energy (kWh)', fontsize=10)
        ax2.grid(True, alpha=0.5, color=colors['grid'], linestyle='-', linewidth=0.8)
        
        # CO2 emissions per epoch plot (bottom right)
        ax3 = fig.add_subplot(gs[1, 1])
        ax3.bar(df['epoch'], df['co2_kg'], color=colors['co2'], alpha=0.7)
        ax3.set_title('CO2 Emissions per Epoch', pad=10, fontsize=12, color=colors['primary'])
        ax3.set_xlabel('Epoch', fontsize=10)
        ax3.set_ylabel('CO2 (kg)', fontsize=10)
        ax3.grid(True, alpha=0.5, color=colors['grid'], linestyle='-', linewidth=0.8)
        
        # Save plot
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=600, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        plt.close()
        
        return {'combined_plots': buf}

def generate_report_from_log(log_file_path, output_path):
    # Read and parse log
    with open(log_file_path, 'r') as f:
        log_content = f.read()
    
    parser = LogParser(log_content)
    metrics = parser.calculate_energy_metrics()
    plots = parser.generate_plots()
    
    # Create PDF
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=24,
        bottomMargin=72
    )
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=10,
        alignment=1,
        textColor=colors.HexColor('#1A237E')
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=20,
        alignment=1,
        textColor=colors.HexColor('#455A64')
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=12,
        textColor=colors.HexColor('#1A237E')
    )
    normal_style = styles['Normal']
    
    # KPI Table
    kpi_data = [[
        Paragraph(f'<para align="center"><b><font size=16>{metrics["co2_kg"]:.3f} kg</font></b><br/><font size=10>CO2eq Emissions</font><br/><font size=8>Carbon Intensity: {parser.carbon_intensity:.2f} gCO2/kWh</font></para>', normal_style),
        Paragraph(f'<para align="center"><b><font size=16>{metrics["energy_kwh"]:.3f} kWh</font></b><br/><font size=10>Total Energy</font><br/><font size=8>Average Power: {metrics["total_power"]:.1f} W</font></para>', normal_style),
        Paragraph(f'<para align="center"><b><font size=16>{format_duration(metrics["total_duration"])}</font></b><br/><font size=10>Training Duration</font><br/><font size=8>Total Epochs: {len(parser.epochs)}</font></para>', normal_style)
    ]]
    
    kpi_table = Table(kpi_data, colWidths=[2.1*inch, 2.1*inch, 2.1*inch], rowHeights=1.1*inch)
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#E8EAF6')),
        ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#1A237E')),
        ('INNERGRID', (0, 0), (-1, -1), 1, colors.HexColor('#C5CAE9')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))

    # Location Bar
    location_bar = Table(
        [[Paragraph(f'<b>Location:</b> {parser.location}', normal_style)]],
        colWidths=[6.3*inch]
    )
    location_bar.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F5F5FA')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1A237E')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#C5CAE9'))
    ]))

    # Parse hardware components
    gpu_name = "-"
    cpu_name = "-"
    if parser.components:
        gpu_match = re.search(r'GPU with device\(s\) ([^\.]+)', parser.components)
        cpu_match = re.search(r'CPU with device\(s\) ([^\.]+)', parser.components)
        if gpu_match:
            gpu_name = gpu_match.group(1).strip()
        if cpu_match:
            cpu_name = cpu_match.group(1).strip()

    # System Power Table
    system_power_data = [
        [Paragraph('<b>System Power</b>', normal_style), ''],
        ['GPU Power', f'{metrics["avg_gpu_power"]:.1f} W ({gpu_name})'],
        ['CPU Power', f'{metrics["avg_cpu_power"]:.1f} W ({cpu_name})'],
        ['Average Power', f'{metrics["total_power"]:.1f} W'],
        ['PUE Coefficient', f'{parser.pue:.2f}']
    ]
    
    system_power_table = Table(system_power_data, colWidths=[2.5*inch, 3.8*inch])
    system_power_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#E8EAF6')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1A237E')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#C5CAE9')),
        ('SPAN', (0, 0), (1, 0)),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ]))

    # Build document
    story = [
        Paragraph("Carbon Emissions Report", title_style),
        Paragraph(
            f"Generated by CarbonTracker v{parser.version} • {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            subtitle_style
        ),
        Spacer(1, 12),
        Paragraph("Summary", heading_style),
        kpi_table,
        Spacer(1, 12),
        location_bar,
        Spacer(1, 18),
        system_power_table,
        Spacer(1, 20),
        Paragraph("Resource Consumption Analysis", heading_style),
        Image(plots['combined_plots'], width=6*inch, height=3.6*inch)
    ]
    
    doc.build(story)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python report.py <log_file_path> <output_pdf_path>")
        sys.exit(1)
    
    generate_report_from_log(sys.argv[1], sys.argv[2]) 