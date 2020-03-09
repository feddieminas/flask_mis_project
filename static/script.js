$(document).ready(function() {
    
    //Ipad pro font-size due to height
    $(window).on('resize', function(){
        const h = window.innerHeight;
        if (h >= 1100) {
            $("body").css({'font-size' : '1.23rem'});
        }
        else {
            $("body").css({'font-size' : 'inherit'});
        }
    }).resize();

    const current = location.pathname;

    // applies to all HTML files, underline the link of your current URL
    $('#menu li a').each(function(){
        if (current=="/") {
            return false;
        };

        if($(this).attr('href').indexOf(current) !== -1){
            $(this).addClass('active');
        } else {
            $(this).removeClass('active');
        };       
    });

    // ADMIN.HTML - flash message insert colour when displays please login
    if ($(".alert-message")[0]){
        $("div.alert-message").addClass("bg-light py-1 pl-4")
    };

    // INDEX.HTML
    $('#country').on("change", function() {
        $('#tax').val(0);
        taxJSonCl.forEach((e, i) => {
            if(e.COUNTRY==$('#country').val()) {
                $('#tax').val((e.TAX * 100).toFixed(1));
                return false
            }
        });
    });

    $('#beta').on("change", function() {
        if ($(this).children("option:selected").val() === "0") {
            $("#beta_manual").prop('disabled', false);
            $("#beta_manual").val("0.00");
        } else {
            $("#beta_manual").prop('disabled', true);
            $("#beta_manual").val(null);
        }
    });    

    // PANEL.HTML - bootstrap multi-select region
    $('#regionSel').multiselect({
        buttonClass: 'btn btn-outline-dark mt-3',
        buttonContainer : '<div class="dropdown" />',
        templates: {
                li: '<li class="dropdown-item"><a><label class="m-0 ml-1 pl-3 pr-0"></label></a></li>',
                ul: '<ul class="multiselect-container dropdown-menu p-1 m-0"></ul>'
        },
        nonSelectedText:'ALL REGIONS',
        buttonWidth: '222px',
        onChange: function(option, checked, select) {
            console.log($(option), $(option).val(), checked, select); // print bootstrap multiselect options
        }       
    });

    if (typeof filtered !== 'undefined') {
        if (filtered) {
            let lookup = {};
            let result = new Array();
            for (let item, i = 0; item = crpJSonCl[i++];) {
                let name = item.REGION;
                if (!(name in lookup)) {
                    lookup[name] = 1;
                    result.push(name);
                };
            };

            let filterselect = new Array();
            $.each($("#regionSel option"), function(i){
                const myTitle= $("#regionSel option")[i].innerText;
                const anyMatch = result.filter(res => res == myTitle).length;
                if (anyMatch) {
                    filterselect.push($("#regionSel option")[i].value);
                };            
            }); 

            $('#regionSel').multiselect('select', filterselect);
        } else {
            // $('#regionSel').multiselect('select', ['1', '2', '3', '4', '5']); // bootstrap multiselect check at all options, opposite is deselect
            // $('#regionSel').multiselect('refresh');
        };     
    };

    // PANEL.HTML - search value on change at the table. search by country
    $('#search').on("keyup", function() {
        // my search value
        const searchField = $('#search').val();
        $filteredOptions.length = 0;

        // if nothing was entered, then return all values filtered by region
        // , otherwise filtered by search value
        if (searchField==null || searchField===false) {
            $filteredOptions = crpJSonCl;
        } else {
            const regex = new RegExp(searchField, "i");
            $.each(crpJSonCl, function(key, val){
                if (val.COUNTRY.search(regex) != -1) {
                    $filteredOptions.push(val);
                }
            });
        };
        
        // search results appear, show all link pages, otherwise not any page exist, there are no records
        if ($filteredOptions.length > 0) {
            $.each($("a.page-link"), function(){
                $(this).css({'display': ''});
            }); 
        } else {
            $.each($("a.page-link"), function(){
                $(this).css({'display': 'none'});
            });             
        }

        // number of pages filtered
        const pages = Math.ceil($filteredOptions.length / page_limit);

        // insert your new hrefs with your function and display none your pages that exceed the filtered records
        $.each($("a.page-link"), function(i){
            let myPage = $("a.page-link")[i].text;
            if (/[0-99]/.test(myPage)) { // it is a page
                $("a.page-link")[i].href = "javascript:srchPagin(" + parseInt(myPage) + ")";
                if (myPage>pages && pages>0) {$(this).css({'display': 'none'});};
            };
        });    

        // fire up the first page
        $('a.page-link')[1].click();
    });  

    // PANEL.HTML - COE Calculation - Beta and Weights playground
    function _p2f_or_na(val) {
        if (val == "NA") {
            return "NA";
        } else {
            return parseFloat(String(val).slice(0, -1));
        }
    }

    function _conv_percent_or_na(val) {
        if (isNaN(val)) {
            return "NA";
        } else {
            val*= 100;
            return val.toFixed(2) + '%';
        }
    }    

    $('#coe_btn').bind('click', function() {
      $.getJSON($SCRIPT_ROOT + '/panel/_add_numbers', {
            w: $("#weights_panel").val(),
            b: $("#beta_panel").val()
      }, function(data) {
            //console.log(data.result); // result to true

            // BETA
            b = parseFloat($("#beta_panel").children("option:selected").text().split("|").map(item => item.trim())[1]);

            // WTS
            filt_wts = wtsJSon.filter(w => w.WT == $("#weights_panel").children("option:selected").text());
            let wts_dict = {};
            for (let i = 0; i < filt_wts.length; i++) {
                wts_dict[filt_wts[i].METHOD.toUpperCase() + "_" + filt_wts[i].CATEGORY.toUpperCase() + "_" + filt_wts[i].TYPE.toUpperCase()] = filt_wts[i].WT_PRICE;
            };
            filt_wts.length = 0;

            // CRP
            coe_td_index = {};
            $.each(crpJSonCl, function(i) {
                coe_td_index[crpJSonCl[i].COUNTRY.toUpperCase() + "_" + crpJSonCl[i].METHOD.toUpperCase() + "_" + crpJSonCl[i].TYPE.toUpperCase() + "_" + crpJSonCl[i].CATEGORY.toUpperCase()] = i;
                if (crpJSonCl[i].CRP_PRICE != "NA") {
                    crpJSonCl[i].COE_PRICE = _conv_percent_or_na(
                        (wts_dict[crpJSonCl[i].METHOD.toUpperCase() + "_" + crpJSonCl[i].CATEGORY.toUpperCase() + "_" + crpJSonCl[i].TYPE.toUpperCase()]
                            + (b * erpJSon[0][crpJSonCl[i].METHOD.toUpperCase() + "_" + crpJSonCl[i].CATEGORY.toUpperCase() + "_" + crpJSonCl[i].TYPE.toUpperCase()])
                        ) + _p2f_or_na(crpJSonCl[i].CRP_PRICE)/100
                    );
                } else {
                    crpJSonCl[i].COE_PRICE = "NA";
                }
            });
            wts_dict = {};

            // loop through last td of a tr
            $("tbody tr").each(function (i, val) { 
                let crpJSonCl_index = coe_td_index[
                    $(this).children('td')[1].innerText.toUpperCase() + "_" +
                    $(this).children('td')[3].innerText.toUpperCase().split(" ").join("_") + "_" +
                    $(this).children('td')[4].innerText.toUpperCase()
                ];
                $(this).children("td:last-child").each(function (j, val) {
                    val.innerText = crpJSonCl[parseInt(crpJSonCl_index)].COE_PRICE;
                });
            });
            coe_td_index = {};
      });

      return false;
    });

});