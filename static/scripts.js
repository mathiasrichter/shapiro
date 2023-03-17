window.addEventListener('DOMContentLoaded', event => {

    var navbarShrink = function () {
        const navbarCollapsible = document.body.querySelector('#mainNav');
        if (!navbarCollapsible) {
            return;
        }
        if (window.scrollY === 0) {
            navbarCollapsible.classList.remove('navbar-shrink')
        } else {
            navbarCollapsible.classList.add('navbar-shrink')
        }

    };

    // Shrink the navbar 
    navbarShrink();

    // Shrink the navbar when page is scrolled
    document.addEventListener('scroll', navbarShrink);

});

var resetTable = function() {
    $('#schemaList').DataTable().destroy();
    setSchemaTable()    
}

var showError = function(title, msg)
{
    var errorModal = new bootstrap.Modal(document.getElementById('errorModal'), {
        keyboard: false
      });
    $("#errorModalTitle").html(title);
    $( "#errorModalContent" ).html(msg);
    errorModal.show()
}

var query = function()
{
    // as per https://stackoverflow.com/questions/32713612/jquery-datatables-destroy-re-create
    if ( $.fn.DataTable.isDataTable('#resultList') ) 
    {
        $('#resultList').DataTable().destroy();
    }
    $('#resultList tbody').empty();
    $('#resultList thead').empty();
    $( "#errorModalContent" ).html( "" );
    var k = $.ajax({
        method: 'POST',
        url: '/query/',
        data: $('#sparqlQuery').val(),
        error: function(response, status, error) 
        {
            var msg = "No error details available."
            try 
            {
                msg = $.parseJSON(response.responseText).err_msg
            } catch (error)
            {
                msg = response.responseText
                if (msg == "" || msg == null)
                {
                    msg = response.status + " - " + response.statusText
                    if ( msg == "0 - error")
                    {
                        msg = "No error details available. Is the server running?"
                    }
                }
            }
            showError("Could not execute SPARQL Query", msg );
        },
        success: function(data, text, jxqr) 
        {
            try 
            {
                data = $.parseJSON(data)
                cols = [{title: "Query did not yield any data"}]
                if (data.length > 0)
                {
                    cols=[]
                    e = data[0]
                    keys=Object.keys(e)
                    for (k in keys)
                    {
                        cols.push(
                            {
                                title:keys[k], 
                                data:keys[k],
                                render: function(data, type, row, meta)
                                        {
                                            if (type === 'display')
                                            {
                                                if (data.toString().startsWith("http"))
                                                {
                                                    return '<a href="' + data + '">'+ data +'</a>'
                                                } else
                                                {
                                                    return data
                                                }
                                            }
                                            return data;
                                        }
                            }
                        )
                    }
                }
                $('#resultList').DataTable( 
                    {
                        destroy: true,
                        data: data,
                        columns: cols
                    }
                );
            } catch ( error )
            {
                showError("Error processing SPARQL Result", error.toString())
            }
        }
    });
}

var setSchemaTable = function(search_text)
{
    if (search_text == undefined)
    {
        url = '/schemas/'
    } else
    {
        url = '/search/?query='+search_text
    }
    $('#schemaList').DataTable(
        {
            'ajax': 
            {
                'url': url, 
                'dataSrc': 'schemas'
            },
            'columns': [
                {
                    'data': 'link',
                    'render': function(data, type, row, meta)
                    {
                        if (type === 'display')
                        {
                            return '<a href="' + data + '">'+data.substring(window.location.origin.length+1, data.length)+'</a>'
                        }
                        return data;
                    }
                }, 
                {'data': 'full_name'},
                {
                    'data': 'link',
                    'orderable': false,
                    'render': function(data, type, row, meta)
                    {
                        if (type === 'display')
                        {
                            return codeIconButton(data)
                        }
                        return data;
                    }
                }
            ]
        });
};

var setBadSchemaTable = function()
{
    url = '/badschemas/'
    $('#badSchemaList').DataTable(
        {
            'ajax': 
            {
                'url': url, 
                'dataSrc': 'badschemas'
            },
            'columns': [
                { 'data': 'name' }, 
                { 'data': 'reason' }
            ]
        });
};
var codeIconSvg = function() 
{
    // https://icons.getbootstrap.com/icons/code-square/
    return '<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"16\" height=\"16\" fill=\"currentColor\" class=\"bi bi-code-square\" viewBox=\"0 0 16 16\"><path d=\"M14 1a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H2a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1h12zM2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2H2z\"/><path d=\"M6.854 4.646a.5.5 0 0 1 0 .708L4.207 8l2.647 2.646a.5.5 0 0 1-.708.708l-3-3a.5.5 0 0 1 0-.708l3-3a.5.5 0 0 1 .708 0zm2.292 0a.5.5 0 0 0 0 .708L11.793 8l-2.647 2.646a.5.5 0 0 0 .708.708l3-3a.5.5 0 0 0 0-.708l-3-3a.5.5 0 0 0-.708 0z\"/></svg>'
}

var codeIconButton = function(link)
{
    return '<button class=\"btn btn-secondary px-1 py-0 mx-0 my-0\" data-bs-toggle=\"modal\" data-bs-target=\"#codeModal\" type=\"button\" onclick=\"viewCode(\'' + link.toString() + '\')\">' + codeIconSvg() + '</button>'
}

var viewCode = function(link)
{
    $.ajaxSetup({
        headers:{
           'Accept': "text/turtle"
        }
     });    
    $.get( link, function( data ) {
        $("#codeModalTitle").html(link.substring(window.location.origin.length, link.length))
        code = Prism.highlight(data, Prism.languages.turtle, 'turtle')
        $( "#codeModalContent" ).html( code );
      });
}

var search = function()
{
    $('#schemaList').DataTable().destroy();
    setSchemaTable($('#searchText').val())
    if ($('#searchText').val() != undefined && $('#searchText').val() != '')
    {
        $('#schemaTableHeader').text('Search Results for ' + $('#searchText').val())
    } else 
    {
        $('#schemaTableHeader').text('Currently Serving');
    }
}

var reset = function()
{
    resetTable();
    $('#schemaTableHeader').text('Currently Serving');
    $('#searchText').val('')
}