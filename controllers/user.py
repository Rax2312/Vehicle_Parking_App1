from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.models import User, ParkingLot, ParkingSpot, Reservation, db
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy.orm import joinedload

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
@login_required
def dashboard():
    user = current_user
    return render_template('user_dashboard.html', user=user)

@user_bp.route('/view-parking-lots')
@login_required
def view_parking_lots():
    user = current_user
    lots = ParkingLot.query.options(joinedload(ParkingLot.spots)).all()
    spot_ids = [spot.id for lot in lots for spot in lot.spots]
    active_reservations = Reservation.query.filter(Reservation.spot_id.in_(spot_ids), Reservation.status == 'Active').all()
    spot_to_user = {r.spot_id: r.user_id for r in active_reservations}
    spots_by_lot_id = {}
    available_spots_by_lot_id = {}
    lots_data = []
    for lot in lots:
        spots_serialized = []
        for spot in lot.spots:
            is_occupied = spot.id in spot_to_user
            reserved_by_user = spot_to_user.get(spot.id) == user.id
            spots_serialized.append({
                'is_occupied': is_occupied,
                'spot_number': spot.spot_number,
                'id': spot.id,
                'floor': spot.floor,
                'status': spot.status,
                'reserved_by_user': reserved_by_user
            })
        spots_by_lot_id[lot.id] = spots_serialized
        available_spots_by_lot_id[lot.id] = len([spot for spot in spots_serialized if not spot['is_occupied']])
        lots_data.append({
            'id': lot.id,
            'prime_location_name': lot.prime_location_name,
            'address': lot.address,
            'available_spots': available_spots_by_lot_id[lot.id],
            'total_spots': len(spots_serialized),
            'price_per_hour': lot.price,
            'pin_code': lot.pin_code
        })
    return render_template('user_viewspots.html', user=user, lots=lots, spots_by_lot_id=spots_by_lot_id, available_spots_by_lot_id=available_spots_by_lot_id, lots_data=lots_data)

@user_bp.route('/booking')
@login_required
def booking_page():
    user = current_user
    lots = ParkingLot.query.all()
    for lot in lots:
        lot.spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
    return render_template('user_booking.html', user=user, lots=lots)

@user_bp.route('/quick-book', methods=['POST'])
@login_required
def quick_book():
    user = current_user
    
    # is user flagged?
    if user.flagged:
        flash('Your account has been flagged. Contact admin for support.', 'danger')
        return redirect(url_for('user.booking_page'))
    
    vehicle_number = request.form['vehicle_number'].strip().lower()
    # Check for active reservation for this vehicle number
    existing = Reservation.query.filter_by(user_id=user.id, status='Active').filter(db.func.lower(Reservation.vehicle_number) == vehicle_number).first()
    if existing:
        flash('You already have an active reservation for this vehicle number.', 'warning')
        return redirect(url_for('user.booking_page'))
    # Find first available spot
    available_spot = ParkingSpot.query.filter_by(is_occupied=False).first()
    if available_spot:
        lot = ParkingLot.query.get(available_spot.lot_id)
        res = Reservation(
            user_id=user.id, 
            parking_lot_id=lot.id, 
            spot_id=available_spot.id, 
            vehicle_number=vehicle_number, 
            status='Active', 
            parking_timestamp=datetime.now()
        )
        db.session.add(res)
        available_spot.is_occupied = True
        db.session.commit()
        flash('Spot booked successfully!', 'success')
    else:
        flash('No available spots found.', 'danger')
    return redirect(url_for('user.booking_page'))

@user_bp.route('/book-lot/<int:lot_id>', methods=['POST'])
@login_required
def book_lot(lot_id):
    user = current_user
    
    if user.flagged:
        flash('Your account has been flagged. Contact admin for support.', 'danger')
        return redirect(url_for('user.booking_page'))
    
    vehicle_number = request.form['vehicle_number'].strip().lower()
    # active reservation for this vehicle number
    existing = Reservation.query.filter_by(user_id=user.id, status='Active').filter(db.func.lower(Reservation.vehicle_number) == vehicle_number).first()
    if existing:
        flash('You already have an active reservation for this vehicle number.', 'warning')
        return redirect(url_for('user.booking_page'))

    available_spot = ParkingSpot.query.filter_by(lot_id=lot_id, is_occupied=False).first()
    if available_spot:
        lot = ParkingLot.query.get(lot_id)
        res = Reservation(
            user_id=user.id, 
            parking_lot_id=lot.id, 
            spot_id=available_spot.id, 
            vehicle_number=vehicle_number, 
            status='Active', 
            parking_timestamp=datetime.now()
        )
        db.session.add(res)
        available_spot.is_occupied = True
        db.session.commit()
        flash('Spot booked successfully!', 'success')
    else:
        flash('No available spots in this lot.', 'danger')
    return redirect(url_for('user.booking_page'))

@user_bp.route('/reservation-history')
@login_required
def reservation_history():
    user = current_user
    reservations = Reservation.query.filter_by(user_id=user.id).order_by(Reservation.parking_timestamp.desc()).all()
    reservation_list = []
    for res in reservations:
        lot = ParkingLot.query.get(res.parking_lot_id)
        spot = ParkingSpot.query.get(res.spot_id)
        # time difference for active reservations
        if res.status == 'Active':
            time_diff = datetime.now() - res.parking_timestamp
            hours = time_diff.total_seconds() / 3600
            time_str = f"{hours:.1f} hours"
            price = round(hours * lot.price, 2) if lot else None
        else:
            time_str = res.parking_timestamp.strftime('%H:%M')
            price = res.parking_cost if hasattr(res, 'parking_cost') else None
        reservation_list.append({
            'id': res.id,
            'lot_name': lot.prime_location_name if lot else '',
            'address': lot.address if lot else '',
            'spot_label': spot.spot_number if spot else '',
            'vehicle': res.vehicle_number if hasattr(res, 'vehicle_number') else '',
            'date': res.parking_timestamp.strftime('%Y-%m-%d') if hasattr(res, 'parking_timestamp') else '',
            'time': time_str,
            'status': res.status,
            'revenue': price
        })
    return render_template('user_reservationhistory.html', user=user, reservations=reservation_list)

@user_bp.route('/profile-update')
@login_required
def profile_update():
    user = current_user
    return render_template('user_profileupdate.html', user=user)

@user_bp.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    user = current_user
    user.first_name = request.form['first_name']
    user.last_name = request.form['last_name']
    user.email = request.form['email']
    user.phone_number = request.form['phone_number']
    user.address = request.form.get('address', '')
    age_val = request.form.get('age')
    user.age = int(age_val) if age_val and age_val.isdigit() else None
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('user.profile_update'))

@user_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    user = current_user
    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    if not user.check_password(current_password):
        flash('Current password is incorrect.', 'danger')
    elif new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
    else:
        user.set_password(new_password)
        db.session.commit()
        flash('Password changed successfully!', 'success')
        return redirect(url_for('user.profile_update'))

@user_bp.route('/reserve/<int:spot_id>', methods=['POST'])
@login_required
def reserve_spot(spot_id):
    user = current_user
    
    # Check if user is flagged
    if user.flagged:
        flash('Your account has been flagged. Contact admin for support.', 'danger')
        return redirect(url_for('user.dashboard'))
    
    vehicle = request.form['vehicle'].strip().lower()
    # is there active reservation for this vehicle number
    existing = Reservation.query.filter_by(user_id=user.id, status='Active').filter(db.func.lower(Reservation.vehicle_number) == vehicle).first()
    if existing:
        flash('You already have an active reservation for this vehicle number.', 'warning')
        return redirect(url_for('user.dashboard'))
    spot = ParkingSpot.query.get(spot_id)
    if Reservation.query.filter_by(spot_id=spot_id, status='Active').first():
        flash('Spot already occupied.', 'danger')
        return redirect(url_for('user.dashboard'))
    lot = ParkingLot.query.get(spot.lot_id)
    res = Reservation(user_id=user.id, parking_lot_id=lot.id, spot_id=spot.id, vehicle_number=vehicle, status='Active', parking_timestamp=datetime.now())
    db.session.add(res)
    spot.is_occupied = True
    db.session.commit()
    flash('Reservation successful!', 'success')
    return redirect(url_for('user.dashboard'))

@user_bp.route('/cancel/<int:reservation_id>', methods=['POST'])
@login_required
def cancel_reservation(reservation_id):
    user = current_user
    res = Reservation.query.get(reservation_id)
    if res and res.user_id == user.id and res.status == 'Active':
        res.status = 'Cancelled'
        db.session.commit()
        flash('Reservation cancelled.', 'info')
    return redirect(url_for('user.reservation_history'))

@user_bp.route('/release-spot/<int:reservation_id>', methods=['POST'])
@login_required
def release_spot(reservation_id):
    user = current_user
    res = Reservation.query.get(reservation_id)
    if res and res.user_id == user.id and res.status == 'Active':
        res.status = 'Released'
        res.leaving_timestamp = datetime.now()
        # final cost
        time_diff = res.leaving_timestamp - res.parking_timestamp
        hours = time_diff.total_seconds() / 3600
        lot = ParkingLot.query.get(res.parking_lot_id)
        res.parking_cost = hours * lot.price
        # update the spot's occupied status
        spot = ParkingSpot.query.get(res.spot_id)
        if spot:
            spot.is_occupied = False
            db.session.commit()
            print(f"[DEBUG] Spot {spot.id} is_occupied after release: {spot.is_occupied}")
        else:
            db.session.commit()
        flash('Spot released successfully!', 'success')
    return redirect(url_for('user.reservation_history')) 

@user_bp.route('/summary')
@login_required
def summary():
    print('[DEBUG] /user/summary route called')
    user = current_user
    
    # user-specific statistics for charts
    from models.models import ParkingLot, ParkingSpot, Reservation
    from datetime import datetime, timedelta
    
    user_reservations = Reservation.query.filter_by(user_id=user.id).count()
    
    # active vs completed reservations
    active_reservations = Reservation.query.filter_by(user_id=user.id, status='Active').count()
    completed_reservations = user_reservations - active_reservations
    
    # total spending
    user_completed_reservations = Reservation.query.filter(
        Reservation.user_id == user.id,
        Reservation.leaving_timestamp.isnot(None)
    ).all()
    
    total_spending = 0
    for res in user_completed_reservations:
        if res.lot:
            duration = (res.leaving_timestamp - res.parking_timestamp).total_seconds() / 3600
            total_spending += duration * res.lot.price
    
    # recent activity (last 30 days)
    month_ago = datetime.now() - timedelta(days=30)
    recent_activity = Reservation.query.filter(
        Reservation.user_id == user.id,
        Reservation.parking_timestamp >= month_ago
    ).count()
    
    # favorite parking lots
    user_lots_usage = {}
    for res in Reservation.query.filter_by(user_id=user.id).all():
        if res.lot:
            lot_name = res.lot.prime_location_name
            user_lots_usage[lot_name] = user_lots_usage.get(lot_name, 0) + 1
    
    favorite_lots = sorted(user_lots_usage.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Average parking duration
    total_duration = 0
    completed_count = 0
    for res in user_completed_reservations:
        duration = (res.leaving_timestamp - res.parking_timestamp).total_seconds() / 3600
        total_duration += duration
        completed_count += 1
    
    avg_duration = round(total_duration / completed_count, 2) if completed_count > 0 else 0
    
    return render_template('user_summary.html',
                         user=user,
                         user_reservations=user_reservations,
                         active_reservations=active_reservations,
                         completed_reservations=completed_reservations,
                         total_spending=round(total_spending, 2),
                         recent_activity=recent_activity,
                         favorite_lots=favorite_lots,
                         avg_duration=avg_duration) 