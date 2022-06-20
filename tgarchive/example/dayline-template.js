document.write(`
 <ul class="index">
    {% for _, d in dayline.items() %}
     <li class="day-{{ d.slug }}">
      <a href="{{ make_filename(month, d.page) }}#{{ d.slug }}">
       {{ d.date.strftime("%d %b %Y") }} <span class="count">({{ d.count }})</span>
      </a>
     </li>
    {% endfor %}
    </ul>
`);