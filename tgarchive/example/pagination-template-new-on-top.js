document.write(`
    {% for p in range(total_pages, 0, -1) %}
        <li class="class-pagination-{{ p }}">
            <a href="{{ month.slug }}{% if p < total_pages %}_{{ p }}{% endif %}.html">{{ p }}</a>
        </li>
    {% endfor %}					
`);