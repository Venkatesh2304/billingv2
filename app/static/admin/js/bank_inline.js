

const GET_OUTSTANDING_URL = "/app/chequedeposit/get-outstanding"
const ALLOWED_DIFF = 50 ; 

function addEventListeners() { 
    document.querySelectorAll('.field-bill select').forEach((input,i) => {
        input.onchange  = (e) => {
            const id = e.target.value;
            if (id) {
                fetchStaticAmt(id,i);
            }
        };
    });

    document.querySelector('form').addEventListener('submit', function(e) {
        if (!validateAmounts()) {
            e.preventDefault();
        }
    });

    document.querySelectorAll('.field-bill a').forEach((input,i) => {
        const id = input.innerText;
            fetchStaticAmt(id,i);
    });
}

// Deprcated function  , we are using only static mat fetch 
// function fetchAmt(id,i) {
//     fetch(`${GET_OUTSTANDING_URL}/${id}/`)
//         .then(response => response.json())
//         .then(data => {
//             console.log( data.party,  data.balance )
//             document.querySelectorAll('input[name$="balance"]')[i].value = data.balance ;
//             document.getElementById("collection-group").querySelectorAll('input[name$="party"]')[i].value = data.party ;
//             document.getElementById("collection-group").querySelectorAll('input[name$="amt"]')[i].value = data.balance ;
//         })
//         .catch(error => console.error('Error fetching amt:', error));
// }

function fetchStaticAmt(id,i) {
    fetch(`${GET_OUTSTANDING_URL}/${id}/`)
        .then(response => response.json())
        .then(data => {
            document.querySelectorAll('.field-balance')[i].innerText = data.balance ;
            const amt_input = document.getElementById("collection-group").querySelectorAll('.field-amt')[i].querySelector("input")
            console.log(amt_input.value)
            if (amt_input.value == "") { amt_input.value = parseInt(data.balance) ; }
            console.log(amt_input.value)
            document.getElementById("collection-group").querySelectorAll('.field-party')[i].innerText = data.party ;
        })
        .catch(error => console.error('Error fetching amt:', error));
}

function validateAmounts() {

    const coll_type =  document.getElementById("id_type") ; 
    if ( coll_type ) { 
        if(coll_type.value == "neft") { 
            const txt = document.querySelector('div.field-amt').innerText ; 
            const chequeAmount = parseFloat( txt.slice(4) );
            return BaseValidateAmounts(chequeAmount);
        }
        if ( (coll_type.value == "cheque") && (document.querySelector("#id_cheque_entry").value == "") ) { 
            alert("Select a Cheque Deposit Entry");
            return false ; 
        }
    } else { 
        const chequeAmount = parseFloat(document.querySelector('input[name="amt"]').value);
        return BaseValidateAmounts(chequeAmount);
    }
    return true ; 
}

function BaseValidateAmounts(chequeAmount) {
    let totalCollectionAmount = 0;
    document.getElementById("collection-group").querySelectorAll('input[name$="amt"]').forEach((input,idx) => {
        const delete_checkbox = document.querySelectorAll('input[name$="DELETE"]')[idx]
        if (!(delete_checkbox && delete_checkbox.checked)) { 
            const value = parseFloat(input.value);
            if (!isNaN(value)) {
                totalCollectionAmount += value;
            }
        }
    });
    const difference = Math.abs(chequeAmount - totalCollectionAmount);
    if (difference > ALLOWED_DIFF) {
        alert(`Mismatch between total collection amount (${totalCollectionAmount}) and cheque amount (${chequeAmount}). \n Please correct the values.`);
        return false;
    }
    return true;
}

document.addEventListener('formset:added', function() {
    addEventListeners();
})

document.addEventListener('DOMContentLoaded', function() {    
    const hide_function = (id) => {
        const neft_colls = document.querySelector("#collection-group")  ; 
        const matched_chq = document.querySelector(".field-cheque_entry")  ;
        neft_colls.style.display = "none" ; 
        matched_chq.style.display = "none" ; 
        if (id) {
            if ( id == "neft" ) {  neft_colls.style.display = "block" ;  }
            if ( id == "cheque") { matched_chq.style.display  = "block" ;  }
        }
    };
    const id_type = document.querySelector('#id_type') ; 
    if (id_type) { 
        id_type.onchange =  (e) => hide_function(e.target.value) ; 
        hide_function(id_type.value)
    }
    addEventListeners();
});
