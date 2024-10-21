const GET_OUTSTANDING_URL = "/app/bank/get-outstanding"
function addEventListeners() { 
    console.log("Adding Event listener")
    document.querySelectorAll('.field-bill select').forEach((input,i) => {
        input.onchange  = (e) => {
            const id = e.target.value;
            if (id) {
                console.log(id,i)
                fetchStaticAmt(id,i);
            }
        };
    });
    document.querySelectorAll('.field-bill').forEach((input,i) => {
            const id = input.innerText;
            fetchStaticAmt(id,i);
    });
}

function fetchAmt(id,i) {
    fetch(`${GET_OUTSTANDING_URL}/${id}/`)
        .then(response => response.json())
        .then(data => {
            document.querySelectorAll('input[name$="balance"]')[i].value = data.balance ;
            document.querySelectorAll('input[name$="party"]')[i].value = data.party ;
        })
        .catch(error => console.error('Error fetching amt:', error));
}

function fetchStaticAmt(id,i) {
    fetch(`${GET_OUTSTANDING_URL}/${id}/`)
        .then(response => response.json())
        .then(data => {
            document.querySelectorAll('.field-balance')[i].innerText = data.balance ;
            document.querySelectorAll('.field-party')[i].innerText = data.party ;
        })
        .catch(error => console.error('Error fetching amt:', error));
}

document.addEventListener('formset:added', function() {
    addEventListeners();
})


document.addEventListener('DOMContentLoaded', function() {
    addEventListeners();
});
