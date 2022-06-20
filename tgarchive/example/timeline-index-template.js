document.write(`
<ul class="timeline index">
          {% for year, months in timeline.items() | reverse %}
          <li class="">
           <h3 class="year"><a href="{{ months[0].slug }}.html">{{ year }}</a></h3>
           <ul class="months">
            {% for m in months | reverse %}
             <li id="timeline-index-li-{{ m.slug }}" class="">
              <a href="{{ m.slug }}.html">
               {{ m.label }}
               <span class="count">({{ m.count }})</span>
              </a>
             </li>
            {% endfor %}
           </ul>
          </li>
          {% endfor %}
 </ul>
`);