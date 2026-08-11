import cairosvg

svg_code = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>
  <rect width='24' height='24' fill='#ffffff'/>
  <g fill='none' stroke='#4f46e5' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
    <path d='M19 11a5 5 0 01-5 5H9.5a5.5 5.5 0 01-5.5-5.5V10A5.5 5.5 0 019.5 4.5h2A5.5 5.5 0 0117 10v1z'/>
    <circle cx='14' cy='9' r='1' fill='#4f46e5' stroke='none'/>
    <path d='M19 10l2 1v2l-2 1M11 4.5V3M7.5 16.5V19M15.5 16.5V19'/>
  </g>
</svg>"""

cairosvg.svg2png(bytestring=svg_code.encode('utf-8'), write_to='static/icon-192.png', output_width=192, output_height=192)
cairosvg.svg2png(bytestring=svg_code.encode('utf-8'), write_to='static/icon-512.png', output_width=512, output_height=512)
cairosvg.svg2png(bytestring=svg_code.encode('utf-8'), write_to='static/apple-touch-icon.png', output_width=180, output_height=180)
