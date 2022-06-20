document.write(`
    {% for p in range(1, total_pages + 1) %}
        <li class="class-pagination-{{ p }}">
            <a href="{{ month.slug }}{% if p > 1 %}_{{ p }}{% endif %}.html">{{ p }}</a>
        </li>
    {% endfor %}					
`);