# HLSL Proposals

This page contains all current HLSL language proposals.

## Proposal Index

<table>
<thead>
<tr>
<th>Proposal</th>
<th>Title</th>
<th>Author</th>
<th>Sponsor</th>
<th>Status</th>
<th>Planned Version</th>
</tr>
</thead>
<tbody>
{% assign proposals = site.pages | where: "dir", "/proposals/" | sort: "proposal" %}
{% for proposal in proposals %}
{% unless proposal.name == "index.md" %}
{% if proposal.title and proposal.proposal %}
<tr>
<td><a href="{{ proposal.url | relative_url }}">{{ proposal.proposal }}</a></td>
<td>{{ proposal.title }}</td>
<td>{{ proposal.author | default: "TBD" }}</td>
<td>{{ proposal.sponsor | default: "TBD" }}</td>
<td>{{ proposal.status | default: "TBD" }}</td>
<td>{{ proposal.planned_version | default: "TBD" }}</td>
</tr>
{% endif %}
{% endunless %}
{% endfor %}
</tbody>
</table>

## Proposals by Status

### Under Consideration
{% for proposal in proposals %}
{% unless proposal.name == "index.md" %}
{% if proposal.status == "Under Consideration" %}
- [{{ proposal.proposal }} - {{ proposal.title }}]({{ proposal.url | relative_url }}) ({{ proposal.author }})
{% endif %}
{% endunless %}
{% endfor %}

### Under Review
{% for proposal in proposals %}
{% unless proposal.name == "index.md" %}
{% if proposal.status == "Under Review" %}
- [{{ proposal.proposal }} - {{ proposal.title }}]({{ proposal.url | relative_url }}) ({{ proposal.author }})
{% endif %}
{% endunless %}
{% endfor %}

### Accepted
{% for proposal in proposals %}
{% unless proposal.name == "index.md" %}
{% if proposal.status == "Accepted" %}
- [{{ proposal.proposal }} - {{ proposal.title }}]({{ proposal.url | relative_url }}) ({{ proposal.author }})
{% endif %}
{% endunless %}
{% endfor %}

### Completed
{% for proposal in proposals %}
{% unless proposal.name == "index.md" %}
{% if proposal.status == "Completed" %}
- [{{ proposal.proposal }} - {{ proposal.title }}]({{ proposal.url | relative_url }}) ({{ proposal.author }})
{% endif %}
{% endunless %}
{% endfor %}

### Rejected
{% for proposal in proposals %}
{% unless proposal.name == "index.md" %}
{% if proposal.status == "Rejected" %}
- [{{ proposal.proposal }} - {{ proposal.title }}]({{ proposal.url | relative_url }}) ({{ proposal.author }})
{% endif %}
{% endunless %}
{% endfor %}

### Deferred
{% for proposal in proposals %}
{% unless proposal.name == "index.md" %}
{% if proposal.status == "Deferred" %}
- [{{ proposal.proposal }} - {{ proposal.title }}]({{ proposal.url | relative_url }}) ({{ proposal.author }})
{% endif %}
{% endunless %}
{% endfor %}
