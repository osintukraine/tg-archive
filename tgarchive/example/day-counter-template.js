document.write(`
<li class="day" id="{{ day.date.strftime('%Y-%m-%d') }}">
    <span class="title">{{ day.date.strftime("%d %B %Y") }} <span class="count">({{ day.count }} messages)</span></span>
</li>
`);